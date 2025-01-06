# pages/base_dados.py

import streamlit as st
import pandas as pd
from supabase import create_client

supabase_url = "https://qafzyikxuezolusfknpg.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFhZnp5aWt4dWV6b2x1c2ZrbnBnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzU1ODQ0MTksImV4cCI6MjA1MTE2MDQxOX0.0vaJejLHeFkXZKic_qmdLI5NaOPxldnp9lxklmwC94w"
supabase = create_client(supabase_url, supabase_key)

st.set_page_config(page_title="Base de Dados", layout="wide")

def load_data():
   response = supabase.table('produtos_ordenados').select('*').execute()
   return pd.DataFrame(response.data)

def save_data(df):
    # Limpar dados
    df = df.fillna(0)
    df = df.astype({
        'id': 'int',
        'produto': 'str',
        'produtopacote': 'float',
        'ingredientes': 'str',
        'prazovalidade': 'int'
    })
    
    # Obter dados existentes
    current_data = supabase.table('produtos').select('*').execute()
    current_ids = set(row['id'] for row in current_data.data)
    
    # Identificar registros a atualizar/inserir/deletar
    new_ids = set(df['id'].tolist())
    
    # IDs a deletar (estavam no banco mas não estão mais no DataFrame)
    ids_to_delete = current_ids - new_ids
    
    # Deletar registros removidos
    if ids_to_delete:
        for id_to_delete in ids_to_delete:
            supabase.table('produtos').delete().eq('id', id_to_delete).execute()
    
    # Atualizar/inserir registros
    if not df.empty:
        records = df.to_dict('records')
        for record in records:
            supabase.table('produtos').upsert(record).execute()

st.title("Base de Dados de Produtos")

df = load_data()
edited_df = st.data_editor(df, num_rows="dynamic")

if st.button("Salvar Alterações"):
   save_data(edited_df)
   st.success("Dados salvos com sucesso!")
