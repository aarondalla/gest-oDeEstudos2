import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta, date
import calendar
from cloud_db import manage_cloud_ignored_disciplines, salvar_registro_nuvem

def calcular_xp_nivel(total_segundos):
    xp_total = int(total_segundos / 36) 
    niveis = [(0, "Estudante Iniciante", "🌱"), (1000, "Estagiário Dedicado", "🐣"), (5000, "Concurseiro Focado", "🦉"), (15000, "Analista em Formação", "🦁"), (30000, "Mestre da Doutrina", "🧙‍♂️"), (60000, "Promotor Substituto", "🏛️"), (100000, "Promotor Titular", "⚖️"), (200000, "Procurador de Justiça", "👑"), (500000, "Lenda do MPMG", "🌟")]
    titulo = niveis[0][1]; emoji = niveis[0][2]; xp_base = 0; xp_prox = niveis[1][0]
    for i in range(len(niveis)-1):
        if xp_total >= niveis[i][0]: titulo = niveis[i][1]; emoji = niveis[i][2]; xp_base = niveis[i][0]; xp_prox = niveis[i+1][0]
        else: break
    xp_no_nivel = xp_total - xp_base; xp_para_upar = xp_prox - xp_base
    percentual = min(xp_no_nivel / xp_para_upar, 1.0) if xp_para_upar > 0 else 1.0
    return titulo, emoji, xp_total, percentual, xp_prox - xp_total

def calcular_sequencia_inteligente(df):
    if df.empty: return 0
    datas = sorted(df['data'].dt.date.unique(), reverse=True)
    if not datas: return 0
    hoje = date.today(); ultimo_estudo = datas[0]; diff_hoje = (hoje - ultimo_estudo).days
    ativa = False
    if diff_hoje == 0: ativa = True 
    elif diff_hoje == 1: ativa = True 
    elif hoje.weekday() == 0 and diff_hoje <= 3: ativa = True 
    if not ativa: return 0
    seq = 1
    for i in range(len(datas)-1):
        d_atual = datas[i]; d_anterior = datas[i+1]; diff = (d_atual - d_anterior).days
        if diff == 1: seq += 1
        elif d_atual.weekday() == 0 and diff <= 3: seq += 1 
        else: break
    return seq

def renderizar_widget_semana(df, compacto=False):
    hoje = date.today(); inicio_sem = hoje - timedelta(days=hoje.weekday())
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    estudos_sem = set()
    if not df.empty: estudos_sem = set(df[df['data'].dt.date >= inicio_sem]['data'].dt.date.unique())
    html_content = '<div class="week-container">'
    for i, nome_dia in enumerate(dias_semana):
        data_dia = inicio_sem + timedelta(days=i)
        estudou = data_dia in estudos_sem
        eh_hoje = data_dia == hoje
        eh_futuro = data_dia > hoje
        bg = "transparent"; border = "#e0e0e0"; icon = "&nbsp;"; opacity = "1.0"
        if estudou: bg = "rgba(255, 215, 0, 0.2)"; border = "#FFD700"; icon = "✅"
        elif eh_hoje: border = "#1f77b4"; bg = "rgba(31, 119, 180, 0.1)"
        elif eh_futuro: opacity = "0.4"
        else: bg = "rgba(128, 128, 128, 0.1)"
        html_content += f'<div class="day-card" style="background-color: {bg}; border-color: {border}; opacity: {opacity};"><div style="font-weight: bold; font-size: 11px; color: #555;">{nome_dia}</div><div style="font-size: 14px; margin-top: 2px;">{icon}</div></div>'
    html_content += '</div>'
    with st.container():
        if not compacto: st.markdown("#### 🔥 Ritmo da Semana")
        else: st.caption("Sua Semana")
        st.markdown(html_content, unsafe_allow_html=True)
        if compacto:
            seq_atual = calcular_sequencia_inteligente(df)
            st.write("") 
            if seq_atual > 1: st.info(f"🚀 Você está voando! {seq_atual} dias seguidos.", icon="🔥")
            elif hoje in estudos_sem: st.success("Ótimo começo!", icon="✨")
            else: st.warning("Acenda a chama hoje!", icon="💡")
            st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

def renderizar_calendario_conquistas(df, meta_diaria_horas):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    if not df.empty:
        df_mes = df[(df['data'].dt.year == ano) & (df['data'].dt.month == mes)]
        somas_diarias = df_mes.groupby(df_mes['data'].dt.day)['duracao_segundos'].sum() / 3600
    else:
        somas_diarias = pd.Series(dtype=float)
        
    cal = calendar.monthcalendar(ano, mes)
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    nome_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    nome_mes_atual = nome_meses[mes - 1]
    
    html = "<div style='border-radius: 12px; padding: 15px; border: 1px solid rgba(128,128,128,0.2); background-color: rgba(128,128,128,0.05);'>"
    html += f"<h4 style='text-align: center; margin-top: 0; margin-bottom: 15px;'>📅 Conquistas de {nome_mes_atual}</h4>"
    html += "<div style='display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px;'>"
    
    for d in dias_semana:
        html += f"<div style='text-align: center; font-weight: bold; font-size: 12px; opacity: 0.6;'>{d}</div>"
        
    for semana in cal:
        for dia in semana:
            if dia == 0:
                html += "<div></div>" 
            else:
                data_atual = date(ano, mes, dia)
                horas = somas_diarias.get(dia, 0)
                is_hoje = "border: 2px solid #1f77b4; box-shadow: 0 0 8px rgba(31,119,180,0.3);" if data_atual == hoje else ""
                
                if data_atual > hoje:
                    bg = "transparent"; border = "rgba(128,128,128,0.2)"; icon = ""; op = "0.3"; color = "inherit"
                elif horas >= meta_diaria_horas and meta_diaria_horas > 0:
                    bg = "linear-gradient(135deg, #FFD700 0%, #FF8C00 100%)"; border = "#DAA520"; icon = "🏆"; op = "1"; color = "#fff" 
                elif horas > 0:
                    bg = "rgba(31, 119, 180, 0.15)"; border = "rgba(31, 119, 180, 0.4)"; icon = "⏳"; op = "1"; color = "inherit"
                else:
                    bg = "rgba(128,128,128,0.05)"; border = "rgba(128,128,128,0.2)"; icon = ""; op = "0.6"; color = "inherit"
                    
                horas_fmt = f"{int(horas)}h{int((horas % 1) * 60)}m" if horas > 0 else "0h"
                title = f"{dia}/{mes}: {horas_fmt}"
                html += f"<div title='{title}' style='background: {bg}; border: 1px solid {border}; {is_hoje} border-radius: 8px; height: 65px; display: flex; flex-direction: column; justify-content: center; align-items: center; opacity: {op}; color: {color}; transition: transform 0.2s;'>"
                html += f"<div style='font-size: 14px; font-weight: 800;'>{dia}</div>"
                html += f"<div style='font-size: 20px; line-height: 1; margin-top: 2px;'>{icon}</div></div>"
                
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)

def processar_algoritmo_revisao(df):
    if df.empty: return []
    df['data_date'] = df['data'].dt.date
    disciplinas_ocultas = manage_cloud_ignored_disciplines('get')
    
    df_valid = df[(df['detalhes'] != 'Geral') & (~df['disciplina'].isin(disciplinas_ocultas)) & (df['tag'] != 'Questões')].copy()
    revisoes_pendentes = []
    grupos = df_valid.groupby(['disciplina', 'detalhes'])
    
    for (disc, det), grupo in grupos:
        if (grupo['tag'] == 'Arquivado').any(): continue
        grupo = grupo.sort_values('data_date')
        num_revisoes = grupo[grupo['is_revisao'] == 1].shape[0]
        ultima_data = grupo.iloc[-1]['data_date']
        
        prox_data = None; motivo = ""
        if num_revisoes == 0: prox_data = ultima_data + timedelta(days=2); motivo = "1ª Revisão (48h)"
        elif num_revisoes == 1: prox_data = ultima_data + timedelta(days=7); motivo = "2ª Revisão (7d)"
        elif num_revisoes == 2: prox_data = ultima_data + timedelta(days=30); motivo = "3ª Revisão (30d)"
        else: prox_data = ultima_data + timedelta(days=45); motivo = "Manutenção (45d)"
        
        if prox_data <= date.today():
            atraso = (date.today() - prox_data).days
            status_txt = "Para Hoje" if atraso == 0 else f"Atrasado {atraso} dias"
            revisoes_pendentes.append({'disciplina': disc, 'detalhes': det, 'data_limite': prox_data, 'motivo': motivo, 'status': status_txt})
    return sorted(revisoes_pendentes, key=lambda x: x['data_limite'])

def renderizar_revisao_inteligente(df):
    st.markdown("### 🧠 Revisão Inteligente")
    st.caption("Tópicos apenas com 'Questões' são ocultados automaticamente.")
    
    pendentes_completos = processar_algoritmo_revisao(df)
    if not pendentes_completos:
        st.balloons(); st.success("🎉 Tudo limpo! Nenhuma revisão pendente.")
        return
        
    disciplinas_pendentes = sorted(list(set([item['disciplina'] for item in pendentes_completos])))
    c_filtro, _ = st.columns([1, 1])
    with c_filtro:
        disc_filtro = st.selectbox("🔍 Focar na Disciplina:", ["Todas"] + disciplinas_pendentes, key="filtro_rev_disc")
        
    if disc_filtro != "Todas": pendentes = [item for item in pendentes_completos if item['disciplina'] == disc_filtro]
    else: pendentes = pendentes_completos
        
    st.write("") 

    tab_48h, tab_7d, tab_30d, tab_45d = st.tabs(["🌱 Fixação", "🌿 7 Dias", "🌳 30 Dias", "🌲 45 Dias"])
    ciclos_map = {"1ª Revisão (48h)": tab_48h, "2ª Revisão (7d)": tab_7d, "3ª Revisão (30d)": tab_30d, "Manutenção (45d)": tab_45d}
    count_map = {k: 0 for k in ciclos_map.keys()}

    for i, item in enumerate(pendentes):
        tab_destino = ciclos_map.get(item['motivo'])
        if tab_destino:
            count_map[item['motivo']] += 1
            with tab_destino:
                icon_status = "🔴" if "Atrasado" in item['status'] else "🔵"
                data_formatada = item['data_limite'].strftime('%d/%m/%Y')
                label_multiline = f"{icon_status} {item['disciplina']} - {item['detalhes']}\n      📅 Vencimento: {data_formatada} • Status: {item['status']}"
                
                with st.expander(label_multiline):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("✅ Feito (30m)", key=f"btn_done_{i}", type="secondary", use_container_width=True):
                            salvar_registro_nuvem(datetime.now(), datetime.now(), datetime.now() + timedelta(minutes=30), 1800, item['disciplina'], item['detalhes'], "Revisão Rápida", is_revisao=1)
                    with c2:
                        if st.button("⏭️ Pular Ciclo", key=f"btn_skip_{i}", type="secondary", use_container_width=True):
                            salvar_registro_nuvem(datetime.now(), datetime.now(), datetime.now(), 0, item['disciplina'], item['detalhes'], "Pular Ciclo", is_revisao=1)
                    with c3:
                        if st.button("🛑 Arquivar", key=f"btn_arch_{i}", type="secondary", use_container_width=True, help="Ocultar tópico para sempre."):
                            salvar_registro_nuvem(datetime.now(), datetime.now(), datetime.now(), 0, item['disciplina'], item['detalhes'], "Arquivado", is_revisao=1)

    for motivo, tab in ciclos_map.items():
        if count_map[motivo] == 0:
            with tab: st.info(f"Nenhuma pendência aqui.", icon="✨")

def renderizar_badges(df):
    if df.empty: return
    madrugada = df[df['inicio'].astype(str).str.startswith(('00','01','02','03','04','05'))].shape[0] > 0
    fds = df[df['data'].dt.dayofweek >= 5].shape[0] > 0
    consti = df[df['disciplina'] == 'Direito Constitucional']['duracao_segundos'].sum() > 36000 
    veterano = df.shape[0] > 100
    maratonista = df['duracao_segundos'].max() >= (3 * 3600)
    sherlock = df[df['tag'] == 'Questões']['duracao_segundos'].sum() >= (20 * 3600)
    clube5 = df[df['inicio'].astype(str).str.startswith(('04','05'))].shape[0] > 0
    tempo_penal = df[df['disciplina'].isin(['Direito Penal', 'Processo Penal'])]['duracao_segundos'].sum()
    penalista = tempo_penal >= (20 * 3600)

    st.markdown("### 🏆 Sala de Troféus")
    c1, c2, c3, c4 = st.columns(4)
    badges = [("Vigia Noturno", "🦉", madrugada, "Estudou de madrugada"), ("Sem Trégua", "⚔️", fds, "Estudou no fim de semana"), ("Constitucionalista", "📜", consti, "+10h de Const."), ("Veterano", "🎖️", veterano, "+100 Sessões"), ("Maratonista", "🏃", maratonista, "Sessão única > 3h"), ("Sherlock", "🔍", sherlock, "+20h de Questões"), ("Clube das 5", "🌅", clube5, "Início entre 4h-6h"), ("Penalista", "⚖️", penalista, "+20h Penal/Proc.")]
    rows = [badges[i:i+4] for i in range(0, len(badges), 4)]
    for row in rows:
        cols = st.columns(4)
        for i, (nome, icon, ativo, desc) in enumerate(row):
            with cols[i]:
                opacity = "1.0" if ativo else "0.3"; grayscale = "0%" if ativo else "100%"
                border = "2px solid #FFD700" if ativo else "1px solid #ddd"; bg = "rgba(255, 215, 0, 0.1)" if ativo else "rgba(255,255,255,0.05)"
                html_badge = f'<div style="text-align: center; opacity: {opacity}; filter: grayscale({grayscale}); cursor: help; margin-bottom: 10px; padding: 8px; border-radius: 8px; border: {border}; background-color: {bg};" title="{desc}"><div style="font-size: 24px; margin-bottom: 2px; line-height: 1;">{icon}</div><div style="font-size: 11px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{nome}</div></div>'
                st.markdown(html_badge, unsafe_allow_html=True)
