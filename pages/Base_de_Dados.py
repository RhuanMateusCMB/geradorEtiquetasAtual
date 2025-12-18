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
        # ✅ CORRETO: Carregue da mesma tabela que você vai salvar
        response = supabase.table('produtos').select('*').execute()
        df = pd.DataFrame(response.data)
        
        # ✅ Garantir que as colunas existam
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
        # ✅ Limpar dados corretamente
        # Substituir valores vazios nas colunas de texto por string vazia
        df['produto'] = df['produto'].fillna('').astype(str)
        df['ingredientes'] = df['ingredientes'].fillna('').astype(str)
        df['descricao'] = df['descricao'].fillna('').astype(str) if 'descricao' in df.columns else ''
        
        # Substituir valores vazios nas colunas numéricas por 0
        df['produtopacote'] = pd.to_numeric(df['produtopacote'], errors='coerce').fillna(0)
        df['prazovalidade'] = pd.to_numeric(df['prazovalidade'], errors='coerce').fillna(0).astype(int)
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        
        # ✅ Obter dados existentes
        current_data = supabase.table('produtos').select('*').execute()
        current_ids = set(row['id'] for row in current_data.data)
        
        # ✅ Identificar registros a deletar
        new_ids = set(df['id'].tolist())
        ids_to_delete = current_ids - new_ids
        
        # ✅ Deletar registros removidos
        if ids_to_delete:
            for id_to_delete in ids_to_delete:
                supabase.table('produtos').delete().eq('id', id_to_delete).execute()
        
        # ✅ Atualizar/inserir registros em lote (mais eficiente)
        if not df.empty:
            records = df.to_dict('records')
            
            # ✅ Processar em lotes de 100 registros por vez
            batch_size = 100
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                for record in batch:
                    # Remover campos vazios ou inválidos
                    record_clean = {k: v for k, v in record.items() if pd.notna(v) or k in ['produto', 'ingredientes', 'descricao']}
                    supabase.table('produtos').upsert(record_clean).execute()
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao salvar dados: {str(e)}")
        return False

st.title("Base de Dados de Produtos")

# ✅ Carregar dados
df = load_data()

# ✅ Garantir que a coluna 'descricao' esteja visível
colunas_visiveis = ['id', 'produto', 'produtopacote', 'ingredientes', 'prazovalidade', 'descricao']
df = df[colunas_visiveis] if all(col in df.columns for col in colunas_visiveis) else df

# ✅ Editor de dados
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
        "descricao": st.column_config.TextColumn("Descrição", width="large")
    }
)

# ✅ Botão de salvar com feedback visual
if st.button("💾 Salvar Alterações", type="primary"):
    with st.spinner("Salvando dados..."):
        if save_data(edited_df):
            st.success("✅ Dados salvos com sucesso!")
            # ✅ Recarregar a página após 1 segundo
            import time
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Erro ao salvar dados. Verifique os logs acima.")