# ==============================================================================
# GESTÃO DE ESTUDOS - MPMG (ARQUITETURA MODULAR NUVEM)
# ARQUIVO PRINCIPAL (UI / MAESTRO)
# ==============================================================================

import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta, date
import altair as alt

# -- IMPORTANDO NOSSOS MÓDULOS DE NUVEM --
from utils import format_seconds_to_hm, tocar_beep, TAGS_ESTUDO, META_SEMANAL_HORAS, get_listas_aux, get_topicos_por_disciplina
from cloud_db import (carregar_dados_nuvem, manage_cloud_timer, salvar_registro_nuvem, 
                      excluir_registro_nuvem, manage_cloud_ignored_disciplines, desarquivar_topico_nuvem)
from logic import (calcular_xp_nivel, calcular_sequencia_inteligente, renderizar_widget_semana,
                   renderizar_calendario_conquistas, renderizar_revisao_inteligente, renderizar_badges)

# ==============================================================================
# 1. INICIALIZAÇÃO E CSS
# ==============================================================================
st.set_page_config(page_title="Gestão de Estudos (Nuvem)", page_icon="☁️", layout="wide")

try:
    with open("style.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Arquivo style.css não encontrado.")

# Inicializa Sessão Timer
if 'initialized' not in st.session_state:
    st.session_state.update({
        'running': False, 'start_time': None, 'accumulated_time': 0, 
        'initial_start_time': None, 'modo': 'crono', 'tempo_pomodoro': 25, 
        'meta_diaria': 5.0, 'play_beep': False, 'initialized': True
    })
    
    saved_state = manage_cloud_timer('load')
    if saved_state:
        st.session_state.meta_diaria = saved_state.get('meta_diaria', 5.0)
        st.session_state.modo = saved_state.get('modo', 'crono')
        st.session_state.tempo_pomodoro = saved_state.get('tempo_pomodoro', 25)
        if saved_state['status'] == 'running' and saved_state['start_time']:
            st.session_state.running = True
            st.session_state.start_time = saved_state['start_time']
            st.session_state.initial_start_time = saved_state['start_time']
            st.session_state.accumulated_time = saved_state['accumulated'] 
        elif saved_state['status'] == 'paused':
            st.session_state.running = False
            st.session_state.accumulated_time = saved_state['accumulated']

if st.session_state.play_beep: tocar_beep(); st.session_state.play_beep = False

# ==============================================================================
# 2. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.title("📚 Gestão Nuvem")
    st.caption("Arquitetura Modular Pro")
    
    df = carregar_dados_nuvem()
    
    if st.button("🔄 Forçar Recuperação"):
        saved_state = manage_cloud_timer('load')
        if saved_state:
            st.session_state.accumulated_time = saved_state['accumulated']
            st.session_state.meta_diaria = saved_state.get('meta_diaria', 5.0)
            if saved_state['status'] == 'running':
                st.session_state.running = True
                st.session_state.start_time = saved_state['start_time']
            st.rerun()
            
    status = "🔥 **EM FOCO**" if st.session_state.running else "💤 **AGUARDANDO**"
    if st.session_state.running: st.success(status)
    else: st.info(status)
    
    total_historico = df['duracao_segundos'].sum() if not df.empty else 0
    tempo_sessao_atual = (datetime.now() - st.session_state.start_time).total_seconds() if st.session_state.running and st.session_state.start_time else 0
    total_geral_rpg = total_historico + st.session_state.accumulated_time + tempo_sessao_atual
    titulo, emoji_avatar, xp, pct_nivel, falta_xp = calcular_xp_nivel(total_geral_rpg)
    
    st.markdown(f"""<div class="avatar-container"><div class="avatar-emoji">{emoji_avatar}</div><h3 style="margin:0; padding:0; color: #FFD700;">{titulo}</h3></div>""", unsafe_allow_html=True)
    st.progress(pct_nivel)
    st.caption(f"✨ **XP Total:** {xp} | 🚀 **Próximo Nível em:** {falta_xp} XP")
    st.divider()
    
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    seg_hoje = df[df['data'].dt.strftime('%Y-%m-%d') == hoje_str]['duracao_segundos'].sum() if not df.empty else 0
    total_hj = seg_hoje + st.session_state.accumulated_time + tempo_sessao_atual
    
    with st.expander("🎯 Configurar Meta"):
        new_meta = st.slider("Horas:", 1, 12, int(st.session_state.meta_diaria))
        if new_meta != st.session_state.meta_diaria:
            st.session_state.meta_diaria = float(new_meta)
            manage_cloud_timer('save', st.session_state.start_time if st.session_state.running else None, 
                               st.session_state.accumulated_time, st.session_state.modo, 
                               st.session_state.tempo_pomodoro, st.session_state.meta_diaria)
            st.rerun()
            
    st.progress(min(total_hj/(st.session_state.meta_diaria * 3600), 1.0))
    c1,c2=st.columns(2)
    c1.metric("Feito", format_seconds_to_hm(total_hj))
    c2.metric("Falta", format_seconds_to_hm(max((st.session_state.meta_diaria*3600) - total_hj, 0)))
    
    if total_hj >= (st.session_state.meta_diaria * 3600) and (st.session_state.meta_diaria * 3600) > 0:
        if 'last_celebration' not in st.session_state: st.session_state.last_celebration = None
        if st.session_state.last_celebration != date.today():
            st.balloons(); st.toast("🏆 Meta Diária Batida! Parabéns!", icon="🎉"); st.session_state.last_celebration = date.today()

# ==============================================================================
# 3. TELA PRINCIPAL (TABS)
# ==============================================================================
aba_foco, aba_revisao, aba_dash, aba_gestao = st.tabs(["⏱️ Sessão de Estudo", "🧠 Revisão Inteligente", "📊 Desempenho e Métricas", "⚙️ Cadastros e Nuvem"])

with aba_foco:
    renderizar_widget_semana(df, compacto=True)
    
    @st.fragment(run_every=1.0)
    def render_timer():
        st.write(" "); st.write(" ")
        c_mod, c_cfg = st.columns([1,3])
        with c_mod:
            md = st.radio("Modo", ["Cronômetro", "Pomodoro"], horizontal=True, label_visibility="collapsed", index=0 if st.session_state.modo=='crono' else 1, disabled=st.session_state.running, key="radio_modo")
        
        new_mode = 'crono' if md=="Cronômetro" else 'pomodoro'
        if new_mode != st.session_state.modo: st.session_state.modo = new_mode; st.rerun()
        
        if st.session_state.modo == 'pomodoro':
            with c_cfg:
                st.session_state.tempo_pomodoro = st.number_input("Minutos", 1, 120, st.session_state.tempo_pomodoro, label_visibility="collapsed", disabled=st.session_state.running, key="ni_pomo")

        tot = st.session_state.accumulated_time
        if st.session_state.running and st.session_state.start_time: 
            tot += (datetime.now() - st.session_state.start_time).total_seconds()
            
        disp = tot if st.session_state.modo == 'crono' else (st.session_state.tempo_pomodoro*60) - tot
        
        if disp <= 0 and st.session_state.modo == 'pomodoro':
            st.session_state.running=False; st.session_state.accumulated_time = st.session_state.tempo_pomodoro*60; st.session_state.start_time = None; st.session_state.play_beep = True
            manage_cloud_timer('save', None, st.session_state.accumulated_time, st.session_state.modo, st.session_state.tempo_pomodoro)
            st.rerun()

        h,m,s = int(disp//3600), int((disp%3600)//60), int(disp%60)
        color = "#28a745" if st.session_state.modo=='pomodoro' and st.session_state.running else "#1f77b4"
        if not st.session_state.running and st.session_state.modo=='crono': color = "#ffa421"
        st.markdown(f'<div class="timer-text" style="color: {color};">{h:02d}:{m:02d}:{s:02d}</div>', unsafe_allow_html=True)
        st.write(" ")
        
        if not st.session_state.running:
            if st.session_state.accumulated_time == 0:
                if st.button("▶️ INICIAR", type="primary", width="stretch", key="btn_iniciar"):
                    st.session_state.running = True; st.session_state.start_time = datetime.now(); st.session_state.initial_start_time = datetime.now()
                    manage_cloud_timer('save', st.session_state.start_time, 0, st.session_state.modo, st.session_state.tempo_pomodoro)
                    st.rerun()
            else:
                c1, c2 = st.columns(2)
                if c1.button("▶️ RETOMAR", type="primary", width="stretch", key="btn_retomar"):
                    st.session_state.running = True; st.session_state.start_time = datetime.now()
                    manage_cloud_timer('save', st.session_state.start_time, st.session_state.accumulated_time, st.session_state.modo, st.session_state.tempo_pomodoro)
                    st.rerun()
                if c2.button("🗑️ DESCARTAR", width="stretch", key="btn_descartar"):
                    st.session_state.accumulated_time = 0; st.session_state.running = False
                    manage_cloud_timer('clear')
                    st.rerun()
                
                st.divider()
                dl = get_listas_aux(df)
                d = st.selectbox("Disciplina", dl+["Nova..."], key="sb_disc") 
                dfn = st.text_input("Nome", key="txt_nome") if d=="Nova..." else d
                
                lst_tops = get_topicos_por_disciplina(df, dfn); lst_tops.append("➕ Novo Tópico...")
                tsl = st.selectbox("Tópico:", lst_tops, key="sb_top")
                tfin = st.text_input("Digite o novo tópico:", key="txt_novo_top") if tsl=="➕ Novo Tópico..." else tsl
                
                c_tag, c_check = st.columns([3, 1])
                with c_tag:
                    tg = st.radio("Método", TAGS_ESTUDO, horizontal=True, key="radio_tag") 
                with c_check:
                    st.write(""); st.write("")
                    is_rev = st.checkbox("🔄 Revisão?", key="chk_rev_timer")
                
                if st.button("☁️ SALVAR NA NUVEM", type="secondary", width="stretch", key="btn_save_cloud"):
                    if d and tfin: 
                        salvar_registro_nuvem(datetime.now(), st.session_state.initial_start_time if st.session_state.initial_start_time else datetime.now(), datetime.now(), st.session_state.accumulated_time, dfn, tfin, tg, is_revisao=1 if is_rev else 0)
                        st.session_state.accumulated_time = 0
                    else: st.error("Preencha tudo")
        else:
            c1, c2 = st.columns(2)
            if c1.button("⏸️ PAUSAR", width="stretch", key="btn_pause"):
                if st.session_state.start_time:
                    st.session_state.accumulated_time += (datetime.now() - st.session_state.start_time).total_seconds()
                st.session_state.running = False; st.session_state.start_time = None
                manage_cloud_timer('save', None, st.session_state.accumulated_time, st.session_state.modo, st.session_state.tempo_pomodoro)
                st.rerun()
            if c2.button("❌ CANCELAR", width="stretch", key="btn_cancel"):
                st.session_state.running = False; st.session_state.accumulated_time = 0
                manage_cloud_timer('clear')
                st.rerun()
    render_timer()

with aba_revisao:
    renderizar_revisao_inteligente(df)

with aba_dash:
    if df.empty:
        st.info("Nenhum dado na nuvem.")
    else:
        st.markdown("### 🗓️ Filtro de Período")
        c_filtro, _ = st.columns([1, 2])
        with c_filtro:
            per = st.date_input("Analisar dados entre:", (date.today() - timedelta(30), date.today()), label_visibility="collapsed")
        
        if isinstance(per, tuple) and len(per) == 2:
            df_filtrado = df[(df['data'].dt.date >= per[0]) & (df['data'].dt.date <= per[1])].copy()
        else:
            df_filtrado = df.copy() 
            
        tot_filt = df_filtrado['duracao_segundos'].sum()
        dias_filt = df_filtrado['data'].dt.date.nunique()
        med_filt = tot_filt / dias_filt if dias_filt > 0 else 0
        strk = calcular_sequencia_inteligente(df) 
        
        hoje = date.today()
        va = df[(df['data'].dt.date >= hoje - timedelta(6)) & (df['data'].dt.date <= hoje)]['duracao_segundos'].sum()
        vb = df[(df['data'].dt.date >= hoje - timedelta(13)) & (df['data'].dt.date <= hoje - timedelta(7))]['duracao_segundos'].sum()
        dlt = ((va - vb) / vb) if vb > 0 else (1.0 if va > 0 else 0.0)

        st.write("") 
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total no Período", format_seconds_to_hm(tot_filt))
        k2.metric("Média no Período", format_seconds_to_hm(med_filt))
        k3.metric("🔥 Sequência Atual", f"{strk} dias")
        k4.metric("Ritmo (7 dias)", format_seconds_to_hm(va), f"{dlt:.1%}")
        st.markdown("---")

        if df_filtrado.empty:
            st.warning("Nenhum estudo registrado no período selecionado.")
        else:
            sub_tab_gami, sub_tab_analise, sub_tab_raiox = st.tabs(["🎮 Gamificação", "📈 Análise Geral", "🔎 Raio-X por Matéria"])
            
            with sub_tab_gami:
                st.write("")
                c_cal, c_badges = st.columns([3, 2], gap="large")
                with c_cal:
                    renderizar_calendario_conquistas(df, st.session_state.meta_diaria)
                with c_badges:
                    renderizar_badges(df)

                st.divider()
                st.subheader("📅 Consistência Anual (Heatmap)")
                base = pd.DataFrame({'data': pd.date_range(f"{date.today().year}-01-01", f"{date.today().year}-12-31")})
                day_sum = df.groupby(df['data'].dt.date)['duracao_segundos'].sum().reset_index()
                day_sum['data'] = pd.to_datetime(day_sum['data'])
                hm = pd.merge(base, day_sum, on='data', how='left').fillna(0)
                hm['horas'] = hm['duracao_segundos'] / 3600
                st.altair_chart(alt.Chart(hm).mark_rect().encode(
                    x=alt.X('week(data):O', title='Semanas'), y=alt.Y('day(data):O', title=None), 
                    color=alt.Color('horas', scale=alt.Scale(scheme='greens'), legend=None), tooltip=['data', alt.Tooltip('horas', format='.1f')]
                ).properties(height=180), width="stretch")

            with sub_tab_analise:
                st.write("")
                st.markdown("#### 📊 Evolução Diária no Período")
                df_filtrado['ISO'] = df_filtrado['data'].dt.strftime('%Y-%m-%d')
                gr = df_filtrado.groupby('ISO').agg({'duracao_segundos':'sum', 'Horas líquidas':'sum'}).reset_index()
                gr['D'] = pd.to_datetime(gr['ISO']).dt.strftime('%d/%m')
                gr['R'] = gr['duracao_segundos'].apply(format_seconds_to_hm)
                
                base_chart = alt.Chart(gr).encode(x=alt.X('D', title='Data', sort=None), y='Horas líquidas')
                chart_barras = (base_chart.mark_bar() + base_chart.mark_text(dy=-5, color='white').encode(text='R')).interactive()
                st.altair_chart(chart_barras, width="stretch")
                
                st.divider()
                c_disc, c_tag, c_turno = st.columns(3, gap="medium")
                
                with c_disc: 
                    st.markdown("##### 📚 Disciplinas (Horas)")
                    df_disc_sum = df_filtrado.groupby('disciplina')['Horas líquidas'].sum().reset_index().sort_values('Horas líquidas', ascending=False)
                    chart_disc = alt.Chart(df_disc_sum).mark_bar().encode(
                        x=alt.X('Horas líquidas:Q', title=None, axis=alt.Axis(labels=False, ticks=False)),
                        y=alt.Y('disciplina:N', sort='-x', title=None, axis=alt.Axis(labelLimit=200)),
                        color=alt.Color('disciplina:N', legend=None), tooltip=['disciplina', alt.Tooltip('Horas líquidas', format='.1f')]
                    ).properties(height=300)
                    st.altair_chart(chart_disc, width="stretch")
                    
                with c_tag:
                    st.markdown("##### 🏷️ Métodos (Tags)") 
                    st.altair_chart(alt.Chart(df_filtrado).mark_arc(innerRadius=45).encode(
                        theta='sum(Horas líquidas)', color=alt.Color('tag', legend=alt.Legend(orient='bottom', title=None)), 
                        tooltip=['tag', alt.Tooltip('sum(Horas líquidas)', format='.1f')]
                    ).properties(height=300), width="stretch")
                    
                with c_turno:
                    st.markdown("##### 🕒 Turnos")
                    if 'Turno' in df_filtrado.columns:
                        df_turno = df_filtrado.groupby('Turno')['Horas líquidas'].sum().reset_index()
                        if not df_turno.empty:
                            st.altair_chart(alt.Chart(df_turno).mark_arc(innerRadius=45).encode(
                                theta='Horas líquidas', color=alt.Color('Turno', scale=alt.Scale(scheme='category20b'), legend=alt.Legend(orient='bottom', title=None)), 
                                tooltip=['Turno', alt.Tooltip('Horas líquidas', format='.1f')]
                            ).properties(height=300), width="stretch")
                        else: st.caption("Sem dados.")
                    else: st.caption("Sem dados.")

            with sub_tab_raiox:
                st.write("")
                ld = sorted(df_filtrado['disciplina'].unique()) 
                c_seletor, _ = st.columns([1, 1])
                with c_seletor:
                    disc_sel = st.selectbox("Selecione a disciplina para focar:", ld, index=0 if ld else None, key="sb_disc_dash")
                
                if disc_sel:
                    df_disc = df_filtrado[df_filtrado['disciplina'] == disc_sel].copy() 
                    if not df_disc.empty:
                        total_materia = df_disc['duracao_segundos'].sum()
                        topico_foco = df_disc.groupby('detalhes')['duracao_segundos'].sum().idxmax()
                        
                        st.write("")
                        k1, k2 = st.columns(2)
                        k1.metric(f"Total em {disc_sel} (No período)", format_seconds_to_hm(total_materia))
                        k2.metric("Tópico Mais Estudado", topico_foco)
                        st.markdown("---")
                        
                        df_chart = df_disc.groupby(['detalhes', 'tag']).agg({'duracao_segundos':'sum'}).reset_index()
                        df_chart['Horas'] = df_chart['duracao_segundos'] / 3600
                        chart_raiox = alt.Chart(df_chart).mark_bar().encode(
                            x=alt.X('Horas', title='Horas Líquidas (Acumuladas)', stack='zero'), 
                            y=alt.Y('detalhes', title='Tópico', sort='-x', axis=alt.Axis(labelLimit=400)),
                            color=alt.Color('tag', title='Método', legend=alt.Legend(orient='top')), 
                            tooltip=['detalhes', 'tag', alt.Tooltip('Horas', format='.1f')]
                        ).properties(height=max(350, len(df_chart['detalhes'].unique()) * 30)) 
                        st.altair_chart(chart_raiox, width="stretch")

with aba_gestao:
    t1, t2, t3 = st.tabs(["➕ Manual", "🚫 Filtros de Revisão", "📝 Histórico Global"])
    with t1:
        st.markdown("### 📝 Inserção Manual")
        dm = st.date_input("Data", date.today()); dl = get_listas_aux(df)
        ds = st.selectbox("Disciplina:", dl+["Nova..."], key="sb_man")
        dfn = st.text_input("Nome da Disciplina:", key="txt_man") if ds=="Nova..." else ds
        
        lst_tops_man = get_topicos_por_disciplina(df, dfn); lst_tops_man.append("➕ Novo Tópico...")
        tsl = st.selectbox("Tópico:", lst_tops_man, key="top_man")
        tfin = st.text_input("Digite o novo tópico:", key="txt_novo_topico_manual") if tsl == "➕ Novo Tópico..." else tsl
        
        c_tag, c_check = st.columns([3, 1])
        with c_tag:
            tg = st.radio("Método", TAGS_ESTUDO, horizontal=True, key="tag_man")
        with c_check:
            st.write(""); st.write("")
            is_rev_man = st.checkbox("🔄 Revisão?", key="chk_rev_man")
            
        c_h, c_m = st.columns(2)
        hh = c_h.number_input("Horas", 0, 23, 1); mm = c_m.number_input("Minutos", 0, 59, 0)
        
        if st.button("➕ Confirmar Registro", key="btn_add_cloud", type="primary", width="stretch"):
            salvar_registro_nuvem(datetime.combine(dm, datetime.min.time()), datetime.now(), datetime.now(), 
                                  hh*3600+mm*60, dfn, tfin, tg, is_revisao=1 if is_rev_man else 0)
            
    with t2:
        st.markdown("### 1. Ocultar Disciplina Inteira")
        st.caption("Disciplinas nesta lista **nunca** aparecerão na aba de Revisão Inteligente.")
        ign_list = manage_cloud_ignored_disciplines('get')
        dl = get_listas_aux(df)
        disp_disp = [d for d in dl if d not in ign_list]
        
        c_add1, c_add2 = st.columns([3, 1])
        with c_add1:
            disp_to_add = st.selectbox("Selecione para ocultar:", disp_disp, key="sb_add_ign_cloud")
        with c_add2:
            st.write(""); st.write("")
            if st.button("➕ Ocultar", use_container_width=True):
                if disp_to_add:
                    manage_cloud_ignored_disciplines('add', disp_to_add); st.rerun()
        
        if ign_list:
            for d in ign_list:
                c1, c2 = st.columns([4, 1])
                c1.write(f"🛑 **{d}**")
                if c2.button("❌", key=f"rm_ign_cloud_{d}"):
                    manage_cloud_ignored_disciplines('remove', d); st.rerun()
                    
        st.divider()
        st.markdown("### 2. Ocultar Tópico Específico (Arquivado)")
        c_disc, c_top, c_btn = st.columns([2, 2, 1])
        with c_disc:
            disc_arch = st.selectbox("Disciplina:", dl if dl else ["Nenhuma"], key="sb_disc_arch_cloud")
        with c_top:
            tops_arch = get_topicos_por_disciplina(df, disc_arch)
            top_arch = st.selectbox("Tópico:", tops_arch if tops_arch else ["Sem tópicos"], key="sb_top_arch_cloud")
        with c_btn:
            st.write(""); st.write("")
            if st.button("🛑 Arquivar", use_container_width=True, disabled=not tops_arch):
                if top_arch and top_arch != "Sem tópicos":
                    salvar_registro_nuvem(datetime.now(), datetime.now(), datetime.now(), 0, disc_arch, top_arch, "Arquivado", is_revisao=1, is_silent=True)
                    st.toast(f"Tópico arquivado!", icon="🛑"); time.sleep(0.5); st.rerun()
                    
        st.markdown("#### Lista de Tópicos Arquivados:")
        if not df.empty:
            df_arch = df[df['tag'] == 'Arquivado']
            if df_arch.empty:
                st.info("Nenhum tópico específico arquivado.")
            else:
                arch_list = df_arch[['disciplina', 'detalhes']].drop_duplicates().values.tolist()
                for d_arch, t_arch in arch_list:
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"🗂️ **{d_arch}** - {t_arch}")
                    if c2.button("❌ Desarquivar", key=f"rm_arch_c_{d_arch}_{t_arch}"):
                        desarquivar_topico_nuvem(df, d_arch, t_arch)

    with t3:
        st.caption("Dados carregados diretamente do Google Sheets.")
        if not df.empty:
            for i, r in df.sort_values('data', ascending=False).head(20).iterrows():
                c1, c2, c3, c4 = st.columns([2,3,2,1])
                c1.write(r['data'].strftime('%d/%m/%Y'))
                rev_badge = "🔄" if r['is_revisao'] == 1 else ""
                c2.write(f"{r['disciplina']} - {r['detalhes']} {rev_badge}")
                c3.write(format_seconds_to_hm(r['duracao_segundos']))
                if c4.button("🗑️", key=f"del_{r['global_id']}"):
                    excluir_registro_nuvem(r['global_id'])
