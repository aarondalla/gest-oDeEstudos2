import pandas as pd
import numpy as np
import base64
import wave
import io
import uuid
import streamlit as st

DISCIPLINAS_PADRAO = [
    "Direito Constitucional", "Direito Administrativo", "Direito Penal", 
    "Direito Civil", "Processo Penal", "Processo Civil", 
    "Direitos Humanos", "Direitos Difusos e Coletivos", "Direito Tributário", 
    "Direito Empresarial", "Legislação Especial", "Legislação MP", 
    "Revisão Geral", "Questões / Simulados", "Outro"
]
TAGS_ESTUDO = ["Teoria (PDF/Vídeo)", "Lei Seca", "Questões", "Jurisprudência", "Resumo Próprio"]
META_SEMANAL_HORAS = 34.0
NOME_PLANILHA_GOOGLE = "Banco_Dados_Estudos"

def generate_id(prefix="WEB"):
    return f"{prefix}-{str(uuid.uuid4())[:8]}"

def format_seconds_to_hm(seconds):
    if pd.isna(seconds) or seconds == 0: return "0m"
    seconds = int(seconds)
    return f"{seconds // 3600:02d}h{(seconds % 3600) // 60:02d}m"

def gerar_beep_b64(frequencia=440, duracao=0.3, volume=0.15):
    try:
        sample_rate = 44100; t = np.linspace(0, duracao, int(sample_rate * duracao), False)
        audio = (np.sin(frequencia * t * 2 * np.pi) * (32767 * volume)).astype(np.int16)
        virtual_file = io.BytesIO()
        with wave.open(virtual_file, 'wb') as wave_file:
            wave_file.setnchannels(1); wave_file.setsampwidth(2); wave_file.setframerate(sample_rate); wave_file.writeframes(audio.tobytes())
        return base64.b64encode(virtual_file.getvalue()).decode()
    except: return ""

def tocar_beep():
    if s := gerar_beep_b64(): 
        st.markdown(f"""<audio autoplay="true" style="display:none;"><source src="data:audio/wav;base64,{s}" type="audio/wav"></audio>""", unsafe_allow_html=True)

def classificar_turno(hora_inicio_str):
    try:
        if pd.isna(hora_inicio_str): return "Desconhecido"
        hora_str = str(hora_inicio_str).strip()
        if len(hora_str) >= 2:
            h = int(hora_str.split(':')[0])
            if 0 <= h < 6: return "Madrugada (0-6h)"
            elif 6 <= h < 12: return "Manhã (6-12h)"
            elif 12 <= h < 18: return "Tarde (12-18h)"
            else: return "Noite (18-24h)"
    except: pass
    return "Desconhecido"

def get_listas_aux(df):
    if df.empty: return sorted(DISCIPLINAS_PADRAO)
    disc_existentes = [d for d in df['disciplina'].unique().tolist() if d]
    return sorted(list(set(DISCIPLINAS_PADRAO + disc_existentes)))

def get_topicos_por_disciplina(df, disciplina):
    if df.empty: return []
    try: return sorted(df[df['disciplina'] == disciplina]['detalhes'].unique().tolist())
    except: return []
