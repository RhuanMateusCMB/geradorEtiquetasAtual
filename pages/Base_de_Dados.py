# pages/base_dados.py

import streamlit as st
import pandas as pd
from supabase import create_client

supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
supabase = create_client(supabase_url, supabase_key)

st.set_page_config(page_title="Base de Dados", layout="wide")

def load_data():
    try:
        response = supabase.table('produtos').select('*').execute()
        df = pd.DataFrame(response.data)
        
        colunas_necessarias = ['id', 'produto', 'produtopacote', 'ingredientes', 'prazovalidade', 'descricao']
        for col in colunas_necessarias:
            if col not in df.columns:
                df[col] = '' if col in ['produto', 'ingredientes', 'descricao'] else 0
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame(columns=['id', 'produto', 'produtopacote', 'ingredientes', 'prazovalidade', 'descricao'])

def save_data(df):
    try:
        # ✅ Limpar dados
        df['produto'] = df['produto'].fillna('').astype(str)
        df['ingredientes'] = df['ingredientes'].fillna('').astype(str)
        df['produtopacote'] = pd.to_numeric(df['produtopacote'], errors='coerce').fillna(0)
        df['prazovalidade'] = pd.to_numeric(df['prazovalidade'], errors='coerce').fillna(0).astype(int)
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        
        # ✅ Obter IDs existentes
        current_data = supabase.table('produtos').select('id').execute()
        current_ids = set(row['id'] for row in current_data.data)
        
        # ✅ Identificar registros a deletar
        new_ids = set(df['id'].tolist())
        ids_to_delete = current_ids - new_ids
        
        # ✅ Deletar em LOTE (uma única requisição)
        if ids_to_delete:
            # Converte para lista para usar com .in_()
            supabase.table('produtos').delete().in_('id', list(ids_to_delete)).execute()
        
        # ✅ Preparar registros para upsert (SEM loop!)
        if not df.empty:
            records = df[['id', 'produto', 'produtopacote', 'ingredientes', 'prazovalidade']].to_dict('records')
            
            # ✅ UPSERT EM LOTE - UMA ÚNICA REQUISIÇÃO!
            supabase.table('produtos').upsert(records).execute()
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao salvar dados: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return False

st.title("Base de Dados de Produtos")

# Carregar e ordenar dados
df = load_data()

colunas_visiveis = ['id', 'produto', 'produtopacote', 'ingredientes', 'prazovalidade', 'descricao']
df = df[colunas_visiveis] if all(col in df.columns for col in colunas_visiveis) else df

# ✅ Ordenar por ID
df = df.sort_values('id', ascending=True).reset_index(drop=True)

# Editor de dados
edited_df = st.data_editor(
    df, 
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", required=True),
        "produto": st.column_config.TextColumn("Produto", required=True),
        "produtopacote": st.column_config.NumberColumn("Qtd/Pacote", required=True),
        "ingredientes": st.column_config.TextColumn("Ingredientes", width="large"),
        "prazovalidade": st.column_config.NumberColumn("Validade (dias)", required=True),
        "descricao": st.column_config.TextColumn("Descrição (auto)", width="large", disabled=True)
    }
)

# Botão de salvar
if st.button("💾 Salvar Alterações", type="primary"):
    with st.spinner("Salvando..."):
        if save_data(edited_df):
            st.success("✅ Dados salvos!")
            import time
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("❌ Erro ao salvar. Verifique os logs.")