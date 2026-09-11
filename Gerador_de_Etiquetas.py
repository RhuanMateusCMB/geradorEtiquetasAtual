import streamlit as st
import pdfplumber
import math
import re
import io
import os
import shutil
from supabase import create_client
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import PyPDF2
import pandas as pd
import time

supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
supabase = create_client(supabase_url, supabase_key)

st.set_page_config(
   layout="wide", 
   page_title="CMB Etiquetas",
   page_icon="logo.ico"
)

data_fabricacao = st.date_input(label="Data de Fabricação dos Produtos:", format="DD/MM/YYYY")

itens_pedido = []
cliente = None

def extrair_cliente(conteudo_pdf):
   global cliente
   for linha in conteudo_pdf.split('\n'):
       if 'Cliente:' in linha:
           cliente = linha.split(':')[1].strip()
           return cliente
   return None

def extrair_itens_pedido(conteudo_pdf, pacote_dict, nome_dict):
    itens_pedido = []
    
    # Modificando o padrão para capturar ambos os números, mas usar apenas o segundo
    padrao_completo = r'\d+\s+(\d+)\s+(.*?)\s+(\d+[.,]?\d*(?:\s*[gG])?)\s*(UN|UND|KG|kg|Kg|G|g|Un|Und|un|und)?\s+R\$\s*\d+,\d+\s+-----\s+R\$\s*\d+,\d+'
    padrao_sem_nome = r'\d+\s+(\d+)\s+(\d+,?\d*)\s*(UN|UND|KG|kg|Kg|G|g|Un|Und|un|und)\s+R\$\s*\d+,\d+\s+-----\s+R\$\s*\d+,\d+'
    
    for linha in conteudo_pdf.split('\n'):
        try:
            if any(char.isdigit() for char in linha):
                match_completo = re.search(padrao_completo, linha)
                match_sem_nome = re.search(padrao_sem_nome, linha)
                
                if match_completo:
                    # Agora pegamos o código do produto do primeiro grupo
                    id_produto = str(int(match_completo.group(1)))
                    quantidade_str = match_completo.group(3)
                    unidade = match_completo.group(4).upper() if match_completo.group(4) else 'UN'
                elif match_sem_nome:
                    id_produto = str(int(match_sem_nome.group(1)))
                    quantidade_str = match_sem_nome.group(2)
                    unidade = match_sem_nome.group(3).upper() if match_sem_nome.group(3) else 'UN'
                else:
                    continue
                
                # Resto do código permanece igual
                nome_produto = nome_dict.get(id_produto, f"Produto {id_produto}")
                
                if unidade in ['UND', 'UN', 'U', 'Un', 'und', 'Und', 'un']:
                    unidade = 'UN'
                elif unidade in ['KG', 'Kg', 'kg']:
                    unidade = 'KG'
                elif unidade in ['G', 'g']:
                    unidade = 'G'
                
                # Remover pontos antes de converter para float
                quantidade_produto = float(quantidade_str.replace('.', '').replace(',', '.'))
                
                if id_produto in pacote_dict:
                    valor_pacote = pacote_dict[id_produto]
                    if valor_pacote == 0:
                        etiquetas_necessarias = 0
                    elif unidade == 'KG':
                        quantidade_gramas = quantidade_produto * 1000
                        valor_pacote_gramas = valor_pacote * 1000
                        etiquetas_necessarias = math.ceil(quantidade_gramas / valor_pacote_gramas)
                    else:
                        etiquetas_necessarias = math.ceil(quantidade_produto / valor_pacote)
                    
                    item = {
                        'number': id_produto,
                        'id_produto': id_produto,
                        'nome_produto': nome_produto,
                        'quantidade_produto': quantidade_produto,
                        'unidade': unidade,
                        'etiquetas_necessarias': etiquetas_necessarias
                    }
                    itens_pedido.append(item)
                else:
                    st.warning(f"\nAVISO: Produto não encontrado na base de dados: {id_produto}")
        except Exception as e:
            st.error(f"Erro ao processar item do pedido: {str(e)}")
    
    return itens_pedido

def _ajustar_fonte_para_largura(pdf, texto, fonte, tamanho_inicial, largura_max, tamanho_minimo=5):
    tamanho = tamanho_inicial
    while tamanho > tamanho_minimo and pdf.stringWidth(texto, fonte, tamanho) > largura_max:
        tamanho -= 0.5
    return tamanho

def _quebrar_em_linhas(pdf, texto, fonte, tamanho_fonte, largura_max):
    linhas = []
    linha_atual = ""
    for palavra in texto.split():
        candidato = f"{linha_atual} {palavra}".strip()
        if not linha_atual or pdf.stringWidth(candidato, fonte, tamanho_fonte) <= largura_max:
            linha_atual = candidato
        else:
            linhas.append(linha_atual)
            linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)
    return linhas

def _desenhar_titulo(pdf, title, page_width, largura_util, y_topo, tamanho_max, tamanho_minimo=6, max_linhas=2):
    fonte = _ajustar_fonte_para_largura(pdf, title, "Helvetica-Bold", tamanho_max, largura_util, tamanho_minimo)
    if pdf.stringWidth(title, "Helvetica-Bold", fonte) <= largura_util:
        linhas = [title]
    else:
        linhas = _quebrar_em_linhas(pdf, title, "Helvetica-Bold", fonte, largura_util)
        if len(linhas) > max_linhas:
            linhas = linhas[:max_linhas]
            ultima = linhas[-1]
            while len(ultima) > 3 and pdf.stringWidth(ultima.rstrip() + "...", "Helvetica-Bold", fonte) > largura_util:
                ultima = ultima[:-1]
            linhas[-1] = ultima.rstrip() + "..."

    pdf.setFont("Helvetica-Bold", fonte)
    espaco = fonte + 2
    y = y_topo
    for linha in linhas:
        pdf.drawCentredString(page_width / 2, y, linha)
        y -= espaco
    return y

def desenhar_conteudo_etiqueta(pdf, tamanho_etiqueta, page_width, page_height, title, ingredientes, descricao, validade, data_fabricacao):
    if tamanho_etiqueta == "60x40mm":
        margem = 5
        largura_util = page_width - 2 * margem
        texto_fab = f"Fab.: {data_fabricacao}"

        if descricao == "Informações na Embalagem" or descricao == "":
            _desenhar_titulo(pdf, title, page_width, largura_util, page_height - 20, 10)

            fonte_validade = _ajustar_fonte_para_largura(pdf, validade, "Helvetica", 6, largura_util)
            pdf.setFont("Helvetica", fonte_validade)
            pdf.drawCentredString(page_width / 2, 26, validade)

            fonte_fab = _ajustar_fonte_para_largura(pdf, texto_fab, "Helvetica-Bold", 6, largura_util)
            pdf.setFont("Helvetica-Bold", fonte_fab)
            pdf.drawCentredString(page_width / 2, 17, texto_fab)

            pdf.setFont("Helvetica", 5)
            pdf.drawCentredString(page_width / 2, 9, "Fabricado por Baxter Indústria de")
            pdf.drawCentredString(page_width / 2, 3, "Alimentos Ltda CNPJ: 00.558.662/000-81")
        else:
            y = _desenhar_titulo(pdf, title, page_width, largura_util, page_height - 12, 9)

            pdf.setFont("Helvetica", 6)
            pdf.drawCentredString(page_width / 2, y, f"{ingredientes}:")
            y -= 9

            altura_rodape = 34
            altura_disponivel = y - altura_rodape
            fonte_desc = 6
            espaco_linha = fonte_desc + 1.5
            linhas_desc = _quebrar_em_linhas(pdf, descricao, "Helvetica", fonte_desc, largura_util)
            while fonte_desc > 5 and len(linhas_desc) * espaco_linha > altura_disponivel:
                fonte_desc -= 0.5
                espaco_linha = fonte_desc + 1.5
                linhas_desc = _quebrar_em_linhas(pdf, descricao, "Helvetica", fonte_desc, largura_util)

            max_linhas = max(1, int(altura_disponivel // espaco_linha))
            if len(linhas_desc) > max_linhas:
                linhas_desc = linhas_desc[:max_linhas]
                ultima = linhas_desc[-1]
                while len(ultima) > 3 and pdf.stringWidth(ultima.rstrip() + "...", "Helvetica", fonte_desc) > largura_util:
                    ultima = ultima[:-1]
                linhas_desc[-1] = ultima.rstrip() + "..."

            pdf.setFont("Helvetica", fonte_desc)
            for linha in linhas_desc:
                pdf.drawCentredString(page_width / 2, y, linha)
                y -= espaco_linha

            fonte_validade = _ajustar_fonte_para_largura(pdf, validade, "Helvetica", 6, largura_util)
            pdf.setFont("Helvetica", fonte_validade)
            pdf.drawCentredString(page_width / 2, 26, validade)

            fonte_fab = _ajustar_fonte_para_largura(pdf, texto_fab, "Helvetica-Bold", 6, largura_util)
            pdf.setFont("Helvetica-Bold", fonte_fab)
            pdf.drawCentredString(page_width / 2, 17, texto_fab)

            pdf.setFont("Helvetica", 5)
            pdf.drawCentredString(page_width / 2, 9, "Fabricado por: Baxter Indústria de Alimentos")
            pdf.drawCentredString(page_width / 2, 3, "LTDA CNPJ: 00.558.662/000-81")
    else:
        if descricao == "Informações na Embalagem" or descricao == "":
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawCentredString(page_width / 2, page_height - 20, title)

            pdf.setFont("Helvetica", 7)
            pdf.drawString(30, 15, f"{validade}")
            pdf.setFont("Helvetica-Bold", 7)
            pdf.drawString(page_width - 80, 15, f"Fab.: {data_fabricacao}")
            pdf.setFont("Helvetica", 7)
            pdf.drawCentredString(140, 5, "Fabricado por Baxter Indústria de Alimentos Ltda CNPJ: 00.558.662/000-81")
        else:
            parte1 = descricao[:90].strip()
            parte2 = descricao[90:].strip()

            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawCentredString(140, 60, title)
            pdf.setFont("Helvetica", 7)
            pdf.drawCentredString(140, 50, f"{ingredientes}:")

            pdf.setFont("Helvetica", 6)
            pdf.drawCentredString(page_width / 2, page_height - 30, parte1)
            pdf.drawCentredString(page_width / 2, page_height - 40, parte2)

            pdf.setFont("Helvetica", 7)
            pdf.drawString(30, 15, f"{validade}")
            pdf.setFont("Helvetica-Bold", 7)
            pdf.drawString(page_width - 80, 15, f"Fab.: {data_fabricacao}")
            pdf.setFont("Helvetica", 7)
            pdf.drawCentredString(140, 5, "Fabricado por: Baxter Indústria de Alimentos LTDA CNPJ: 00.558.662/000-81")

def carregar_dados_produtos():
   try:
       response = supabase.table('produtos').select('*').execute()
       df_produtos = pd.DataFrame(response.data)
       
       pacote_dict = dict(zip(df_produtos["id"].astype(str), df_produtos["produtopacote"]))
       nome_dict = dict(zip(df_produtos["id"].astype(str), df_produtos["produto"]))
       return pacote_dict, nome_dict
   except Exception as e:
       st.error(f"Erro ao carregar dados: {str(e)}")
       return {}, {}

with st.sidebar:
   st.header("GERADOR DE ETIQUETAS CMB")
   tamanho_etiqueta = st.radio(
       label="Tamanho da Etiqueta:",
       options=["Padrão (9,8x2,5cm)", "60x40mm"],
       index=0
   )
   arquivo_pedido = st.file_uploader(label="Arraste ou Selecione o Arquivo em PDF do Pedido:", type=['pdf'])

   st.divider()
   with st.expander("Adicionar Novo Produto", expanded=False):
       st.subheader("Adicionar Novo Produto")
       novo_id = st.number_input("ID do Produto", min_value=1, step=1)
       novo_produto = st.text_input("Nome do Produto")
       nova_quantidade = st.number_input("Quantidade por Embalagem", min_value=0.0, step=0.1)
       novos_ingredientes = st.text_area("Ingredientes")
       nova_validade = st.number_input("Prazo de Validade (dias)", min_value=1, step=1)
       
       if st.button("Adicionar Produto"):
             try:
                 data = {
                     "id": novo_id,
                     "produto": novo_produto,
                     "produtopacote": nova_quantidade,
                     "ingredientes": novos_ingredientes,
                     "prazovalidade": nova_validade,
                     "descricao": f"Ingredientes: {novos_ingredientes} Válido {nova_validade} dia(s) após a data de fabricação."
                 }
                 supabase.table('produtos').insert(data).execute()
                 st.success("Produto adicionado com sucesso!")
             except Exception as e:
                 st.error(f"Erro ao adicionar produto: {str(e)}")

if arquivo_pedido:
   data_fabricacao = data_fabricacao.strftime("%d/%m/%Y")
   st.success(f"Data de Fabricação dos Produtos: :blue[{data_fabricacao}]")
   
   try:
       arquivo_pedido_bytes = io.BytesIO(arquivo_pedido.read())
       with pdfplumber.open(arquivo_pedido_bytes) as pdf:
           conteudo_pdf = ""
           for pagina in pdf.pages:
               conteudo_pdf += pagina.extract_text()

           cliente = extrair_cliente(conteudo_pdf)
           if cliente:
               st.success(f"Cliente identificado: {cliente}")
           else:
               st.error("Nenhum cliente identificado no PDF.")

           pacote_dict, nome_dict = carregar_dados_produtos()
           itens_pedido = extrair_itens_pedido(conteudo_pdf, pacote_dict, nome_dict)

           pasta_destino = "pedidos"
           if not os.path.exists(pasta_destino):
               os.makedirs(pasta_destino)
           else:
               shutil.rmtree(pasta_destino)
               os.makedirs(pasta_destino)

           if itens_pedido:
               total_etiquetas = sum(item["etiquetas_necessarias"] for item in itens_pedido)
               etiquetas_geradas = 0
               
               progress_bar = st.progress(0)
               status_text = st.empty()

               if tamanho_etiqueta == "60x40mm":
                   page_width = 6.0 / 2.54 * inch
                   page_height = 4.0 / 2.54 * inch
               else:
                   page_width = 9.8 / 2.54 * inch
                   page_height = 2.5 / 2.54 * inch

               for idx, item in enumerate(itens_pedido):
                   produto = item["nome_produto"]
                   quantidade = item["etiquetas_necessarias"]

                   for i in range(quantidade):
                       try:
                           etiquetas_geradas += 1
                           progress = int((etiquetas_geradas / total_etiquetas) * 100)
                           progress_bar.progress(progress)
                           status_text.text(f"Gerando etiqueta {etiquetas_geradas} de {total_etiquetas}")
                           
                           fileName = f"{idx+1:03d}_{cliente}_{produto}_{i+1:03d}.pdf".replace('/', '-').replace(' ', '_')
                           documentTitle = cliente
                           title = produto
                           caminho_completo = os.path.join(pasta_destino, fileName)
                           
                           pdf = canvas.Canvas(caminho_completo)
                           pdf.setPageSize((page_width, page_height))
                           pdf.setTitle(documentTitle)

                           produto_info = supabase.table('produtos').select('*').eq('id', item["id_produto"]).execute()
                           produto_data = produto_info.data[0] if produto_info.data else None
                           
                           if produto_data:
                               descricao_produto = produto_data["descricao"]
                           else:
                               descricao_produto = produto

                           regex = r"(?m)^(.*?)(?::|\.)\s*(.*?)(?::|\.)\s*(.*?)$"

                           match = re.search(regex, descricao_produto)
                           if match:
                               ingredientes = match.group(1).strip()
                               descricao = match.group(2).strip()
                               validade = match.group(3).strip()
                           else:
                               ingredientes = descricao_produto
                               descricao = ""
                               validade = ""

                           if not any(char.isdigit() for char in validade):
                               validade = 'Consumo Diário.'

                           desenhar_conteudo_etiqueta(
                               pdf, tamanho_etiqueta, page_width, page_height,
                               title, ingredientes, descricao, validade, data_fabricacao
                           )
                           pdf.save()
                       except Exception as e:
                           st.error(f"Erro ao gerar etiqueta: {str(e)}")

               merger = PyPDF2.PdfMerger()
               pasta_destino_combinados = "pedidos_combinados"

               if not os.path.exists(pasta_destino_combinados):
                   os.makedirs(pasta_destino_combinados)

               lista_arquivos = sorted(os.listdir(pasta_destino))
               for arquivo in lista_arquivos:
                   if arquivo.endswith(".pdf"):
                       caminho_arquivo = os.path.join(pasta_destino, arquivo)
                       if os.path.isfile(caminho_arquivo):
                           merger.append(caminho_arquivo)

               arquivo_combinado = os.path.join(pasta_destino_combinados, f"{cliente}_etiquetas.pdf".replace('/', '-').replace(' ', '_'))
               merger.write(arquivo_combinado)
               merger.close()

               if lista_arquivos:
                   st.success("Etiquetas geradas com sucesso!")
                   if st.button(label="Preparar o Download"):
                       if os.path.exists(arquivo_combinado):
                           with open(arquivo_combinado, "rb") as file:
                               bytes = file.read()
                               st.download_button(
                                   label="Clique aqui para baixar o PDF gerado", 
                                   data=bytes, 
                                   file_name=f"{cliente}_etiquetas.pdf".replace('/', '-').replace(' ', '_')
                               )
               else:
                   st.warning("Nenhuma etiqueta gerada para impressão.")
               
           st.text("")
           st.text("")

   except Exception as e:
       st.error(f"Ocorreu um erro durante o processamento do arquivo: {str(e)}")

   if st.button("Finalizar Processos"):
       try:
           if os.path.exists(pasta_destino):
               shutil.rmtree(pasta_destino)
           if os.path.exists(pasta_destino_combinados):
               shutil.rmtree(pasta_destino_combinados)
           st.success("Processos Finalizados com Sucesso!")
       except Exception as e:
           st.error(f"Erro ao finalizar processos: {str(e)}")

st.write("##")
st.write("Desenvolvido por CMB Capital")
st.write("© 2024 CMB Capital. Todos os direitos reservados.")
