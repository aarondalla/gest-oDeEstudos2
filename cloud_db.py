import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
from utils import NOME_PLANILHA_GOOGLE, generate_id, classificar_turno

@st.cache_resource
def connect_master_sheet(): 
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        else:
            creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        client = gspread.authorize(creds)
        return client.open(NOME_PLANILHA_GOOGLE)
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

def get_main_worksheet():
    wb = connect_master_sheet()
    return wb.sheet1 if wb else None

def manage_cloud_timer(action, start_time=None, accumulated=0, modo='crono', tempo_pomodoro=25, meta_diaria=None):
    wb = connect_master_sheet()
    if not wb: return None
    meta = meta_diaria if meta_diaria is not None else st.session_state.get('meta_diaria', 5.0)

    try: ws = wb.worksheet("Estado_Timer_V3")
    except:
        ws = wb.add_worksheet(title="Estado_Timer_V3", rows=5, cols=6)
        ws.update('A1:F1', [["status", "start_timestamp", "accumulated_seconds", "modo", "tempo_pomodoro", "meta_diaria"]])
        ws.update('A2:F2', [["stopped", 0, 0, "crono", 25, float(meta)]])

    if action == 'save':
        if start_time: status = "running"
        elif accumulated > 0: status = "paused"
        else: status = "stopped"
        ts = start_time.timestamp() if start_time else 0
        ws.update('A2:F2', [[status, ts, accumulated, modo, tempo_pomodoro, float(meta)]])
        
    elif action == 'clear':
        ws.update('A2:F2', [["stopped", 0, 0, "crono", 25, float(meta)]])
        
    elif action == 'load':
        try:
            row = ws.row_values(2)
            if not row or len(row) < 3: return None
            status = row[0]
            ts_val = float(row[1]) if row[1] else 0
            s_time = datetime.fromtimestamp(ts_val) if ts_val > 0 else None
            acc = float(row[2]) if row[2] else 0
            md = row[3] if len(row) > 3 else 'crono'
            tp = int(row[4]) if len(row) > 4 else 25
            meta_loaded = float(row[5]) if len(row) > 5 else 5.0
            return {'status': status, 'start_time': s_time, 'accumulated': acc, 'modo': md, 'tempo_pomodoro': tp, 'meta_diaria': meta_loaded}
        except: return None

def manage_cloud_ignored_disciplines(action, disciplina=None):
    wb = connect_master_sheet()
    if not wb: return []
    try: ws = wb.worksheet("Disciplinas_Ocultas")
    except:
        ws = wb.add_worksheet(title="Disciplinas_Ocultas", rows=100, cols=1)
        ws.update('A1', [["nome_disciplina"]])
        ws.append_row(["Questões / Simulados"])

    if action == 'get':
        try:
            records = ws.col_values(1)
            return [r.strip() for r in records[1:] if r.strip()]
        except: return []
    elif action == 'add' and disciplina:
        existentes = manage_cloud_ignored_disciplines('get')
        if disciplina not in existentes: ws.append_row([disciplina])
    elif action == 'remove' and disciplina:
        try:
            cell = ws.find(disciplina)
            if cell: ws.delete_rows(cell.row)
        except: pass

def desarquivar_topico_nuvem(df, disciplina, topico):
    sheet = get_main_worksheet()
    if not sheet: return
    try:
        gids_to_delete = df[(df['disciplina'] == disciplina) & (df['detalhes'] == topico) & (df['tag'] == 'Arquivado')]['global_id'].tolist()
        for gid in gids_to_delete:
            cell = sheet.find(gid)
            if cell: sheet.delete_rows(cell.row)
        st.toast(f"Tópico desarquivado!", icon="✅"); time.sleep(0.5); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

def carregar_dados_nuvem():
    sheet = get_main_worksheet()
    if not sheet: return pd.DataFrame()
    try:
        dn_raw = sheet.get_all_values()
        if len(dn_raw) > 1:
            df = pd.DataFrame(dn_raw[1:], columns=dn_raw[0])
            df.columns = [c.strip().lower() for c in df.columns]
            
            # AUTO-PURGE DAS DATAS CORROMPIDAS NA NUVEM
            df['data'] = pd.to_datetime(df['data'], format='mixed', dayfirst=True, errors='coerce')
            df = df.dropna(subset=['data']) 
            if df.empty: return pd.DataFrame(columns=['global_id', 'data', 'inicio', 'fim', 'duracao_segundos', 'disciplina', 'detalhes', 'tag', 'is_revisao'])
            
            df['duracao_segundos'] = pd.to_numeric(df['duracao_segundos'], errors='coerce').fillna(0)
            df['Horas líquidas'] = df['duracao_segundos'] / 3600
            if 'is_revisao' not in df.columns: df['is_revisao'] = 0
            df['is_revisao'] = pd.to_numeric(df['is_revisao'], errors='coerce').fillna(0).astype(int)
            df['disciplina'] = df['disciplina'].astype(str).str.strip()
            df['detalhes'] = df['detalhes'].fillna('Geral')
            df.loc[df['detalhes'] == '', 'detalhes'] = 'Geral'
            
            # RECUPERANDO A COLUNA TURNOS
            if 'inicio' in df.columns: df['Turno'] = df['inicio'].apply(classificar_turno)
            else: df['Turno'] = "Desconhecido"
            
            if 'global_id' not in df.columns: df['global_id'] = [generate_id("OLD_WEB") for _ in range(len(df))]
            return df
        else:
            return pd.DataFrame(columns=['global_id', 'data', 'inicio', 'fim', 'duracao_segundos', 'disciplina', 'detalhes', 'tag', 'is_revisao'])
    except Exception as e:
        st.error(f"Erro ao ler dados: {e}")
        return pd.DataFrame()

def salvar_registro_nuvem(data_obj, inicio, fim, duracao, disciplina, detalhes, tag, is_revisao=0, is_silent=False):
    sheet = get_main_worksheet()
    if not sheet: return
    try:
        new_id = generate_id("WEB")
        d_iso = data_obj.strftime('%Y-%m-%d')
        ini_str = inicio.strftime('%H:%M:%S')
        fim_str = fim.strftime('%H:%M:%S')
        dados_sheet = sheet.get_all_values()
        if len(dados_sheet) == 0:
            sheet.append_row(['global_id', 'data', 'inicio', 'fim', 'duracao_segundos', 'disciplina', 'detalhes', 'tag', 'is_revisao'])
        elif 'is_revisao' not in [c.lower() for c in dados_sheet[0]]:
            sheet.update_cell(1, len(dados_sheet[0])+1, 'is_revisao')
        sheet.append_row([new_id, d_iso, ini_str, fim_str, duracao, disciplina, detalhes, tag, int(is_revisao)])
        
        if not is_silent:
            manage_cloud_timer('clear')
            st.toast("Salvo na nuvem com sucesso!", icon="☁️")
            time.sleep(1)
            st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def excluir_registro_nuvem(global_id_target):
    sheet = get_main_worksheet()
    if not sheet: return
    try:
        cell = sheet.find(global_id_target)
        if cell:
            sheet.delete_rows(cell.row)
            st.toast("Registro excluído.", icon="🗑️"); time.sleep(1); st.rerun()
        else: st.warning("ID não encontrado.")
    except Exception as e: st.error(f"Erro ao excluir: {e}")
