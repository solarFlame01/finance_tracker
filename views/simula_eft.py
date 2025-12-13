import streamlit as st
import pandas as pd
import plotly.graph_objects as go
# Sezione Simula ETF (placeholder)
def render_simula_etf():
    st.header("🔮 Simula ETF")
    
    with st.container():
        st.info("🚧 Sezione in costruzione - Disponibile nella prossima versione")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📊 Simulatore di Investimento")
            
            # Input per simulazione
            capitale = st.number_input(
                "Capitale iniziale (€)",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000
            )
            
            orizzonte = st.slider(
                "Orizzonte temporale (anni)",
                min_value=1,
                max_value=30,
                value=10
            )
            
            rendimento_atteso = st.slider(
                "Rendimento annuo atteso (%)",
                min_value=-5.0,
                max_value=20.0,
                value=7.0,
                step=0.5
            )
            
            volatilita = st.slider(
                "Volatilità annua attesa (%)",
                min_value=5.0,
                max_value=30.0,
                value=15.0,
                step=0.5
            )
        
        with col2:
            st.subheader("📈 Risultati Proiettati")
            
            # Calcolo semplice
            if st.button("Calcola Proiezione", type="primary"):
                # Calcolo interesse composto
                valore_finale = capitale * ((1 + rendimento_atteso/100) ** orizzonte)
                
                st.metric("Valore finale stimato", f"€{valore_finale:,.0f}")
                st.metric("Rendimento totale", f"{(valore_finale/capitale - 1)*100:.1f}%")
                st.metric("Rendimento medio annuo", f"{rendimento_atteso:.1f}%")
        
        # Grafico placeholder per simulazione
        st.subheader("📊 Andamento Simulato")
        fig = go.Figure()
        
        # Genera dati simulati
        anni = list(range(orizzonte + 1))
        valori = [capitale * ((1 + rendimento_atteso/100) ** anno) for anno in anni]
        
        fig.add_trace(go.Scatter(
            x=anni,
            y=valori,
            mode='lines',
            name='Proiezione',
            line=dict(color='green', width=3)
        ))
        
        # Aggiungi banda di volatilità
        if volatilita > 0:
            upper = [val * (1 + volatilita/100) ** anno for anno, val in enumerate(valori)]
            lower = [val * (1 - volatilita/100) ** anno for anno, val in enumerate(valori)]
            
            fig.add_trace(go.Scatter(
                x=anni + anni[::-1],
                y=upper + lower[::-1],
                fill='toself',
                fillcolor='rgba(0,100,80,0.2)',
                line=dict(color='rgba(255,255,255,0)'),
                name='Banda di volatilità'
            ))
        
        fig.update_layout(
            height=400,
            title="Proiezione dell'investimento",
            xaxis_title="Anni",
            yaxis_title="Valore (€)",
            showlegend=True
        )
        
        st.plotly_chart(fig, width='stretch')
