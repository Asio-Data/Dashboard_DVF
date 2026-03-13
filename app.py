import streamlit as st
import pandas as pd
import altair as alt
import plotly.graph_objects as go
from datetime import datetime
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import datetime
import pydeck as pdk
import ast



# --- CONFIGURATION ---
st.set_page_config(page_title="Data Analysis - Immobilier", layout="wide")

# --- CHARGEMENT DES DONNEES ---
@st.cache_data
def load_data():
    colonnes_utiles = [
        'Region', 'Code departement', 'Commune', 'Type local', 
        'Nombre pieces principales', 'Valeur fonciere', 
        'Surface reelle bati', 'Prix_m2', 'Date mutation','Mois_Vente'
    ]
    df = pd.read_parquet("DVF_2024.parquet",columns=colonnes_utiles)
    df_carte = pd.read_parquet('df_simulation_master.parquet')

    df['Code departement'] = df['Code departement'].astype(str)
    df['Nombre pieces principales'] = df['Nombre pieces principales'].astype(int)
    
    df_carte = df_carte.dropna(subset=['polygon', 'prix_simule_m2'])
    if isinstance(df_carte['polygon'].iloc[0], str):
        df_carte['polygon'] = df_carte['polygon'].apply(ast.literal_eval)
    df_carte['prix_simule_m2'] = pd.to_numeric(df_carte['prix_simule_m2'], errors='coerce')
    df_carte = df_carte.dropna()

    return df, df_carte

df, df_carte = load_data()

# --- INITIALISATION DU SESSION STATE ---
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = df

# --- FONCTIONS ---
current_year = datetime.datetime.now().year

# Fonction utilitaire pour la conversion
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# Fonction de la zone d'export comme un fragment isolé
@st.fragment
def section_export(df_filtre):
    st.write("### 📥 Zone d'Exportation")
    
    # Deux colonnes pour le bouton
    col_btn, col_status = st.columns([1, 2])
    
    with col_btn:
        # L'interaction ici ne relancera QUE cette fonction 'section_export'
        if st.button("🛠️ Préparer le fichier CSV", width="stretch"):
            with st.spinner("Génération..."):
                csv = convert_df_to_csv(df_filtre)
                
                st.download_button(
                    label="📥 Télécharger le CSV",
                    data=csv,
                    file_name=f"export_vergers_{datetime.now().strftime('%d%m_%H%M')}.csv",
                    mime='text/csv',
                    width="stretch"
                )
    with col_status:
        st.info("Cliquez pour générer le lien de téléchargement sans recharger la page.")


@st.cache_resource
def build_pydeck_map(prix_max, _df_source):
    df_temp = _df_source.copy()
    df_temp['prix_sature'] = df_temp['prix_simule_m2'].clip(upper=prix_max)

    # Palette
    colors_list = [
        (49/255, 54/255, 149/255), (69/255, 117/255, 180/255), 
        (116/255, 173/255, 209/255), (171/255, 217/255, 233/255), 
        (254/255, 224/255, 144/255), (253/255, 174/255, 97/255), 
        (244/255, 109/255, 67/255), (215/255, 48/255, 39/255), 
        (165/255, 0/255, 38/255)
    ]
    cmap_custom = mcolors.LinearSegmentedColormap.from_list("custom_immo", colors_list)
    norm = mcolors.Normalize(vmin=0, vmax=prix_max)

    def get_color(prix):
        r, g, b, _ = cmap_custom(norm(prix))
        return [int(r * 255), int(g * 255), int(b * 255), 180]

    # Application des couleurs
    df_temp['couleur_rgb'] = df_temp['prix_sature'].apply(get_color)

    couche_polygones = pdk.Layer(
        "PolygonLayer",
        data=df_temp,
        get_polygon="polygon",
        get_fill_color="couleur_rgb",
        filled=True,
        stroked=False,
        pickable=True
    )

    vue_initiale = pdk.ViewState(
        longitude=2.2137,
        latitude=46.2276,
        zoom=5,
        pitch=0,
        bearing=0
    )

    carte_pydeck = pdk.Deck(
        layers=[couche_polygones],
        initial_view_state=vue_initiale,
        map_style="light", 
        tooltip={"text": "Prix estimé : {prix_simule_m2} €/m²"}
    )
    
    return carte_pydeck


# --- BARRE LATÉRALE ---
with st.sidebar:

    st.image("logo_dark.svg", use_container_width=True)
    st.divider()

    st.header("🔍 Filtres de recherche")

    df['Code departement'] = df['Code departement'].astype(str)

    # --- SECTION LOCALISATION (Cascade) ---
    # 1. Région
    regions_dispo = sorted(df['Region'].unique())
    selected_regions = st.multiselect("Regions", options=regions_dispo)
    
    # 2. Département
    if selected_regions:
        depts_dispo = sorted(df[df['Region'].isin(selected_regions)]['Code departement'].unique())
    else:
        depts_dispo = sorted(df['Code departement'].unique())
    
    selected_depts = st.multiselect("Départements", options=depts_dispo)
    
    st.divider()

    # --- SECTION TECHNIQUE ---
    with st.form("filter_form"):
        # Filtre type de bien
        type_bien = sorted(df['Type local'].unique())
        selected_type = st.multiselect("Type de bien", options=type_bien)

        # Filtre nombre de pieces
        nb_piece = sorted(df['Nombre pieces principales'].unique())
        selected_piece = st.multiselect("Nombre de pièces", options=nb_piece)
        
        # Filtre Budget (Slider)
        min_budget = int(df['Valeur fonciere'].min()) 
        max_budget = int(df['Valeur fonciere'].max())
        
        selected_budget = st.slider("Budget", min_budget, max_budget, (min_budget, max_budget))

        # Filtre Surface (Slider)
        min_surface = int(df['Surface reelle bati'].min()) 
        max_surface = int(df['Surface reelle bati'].max())
        
        selected_surface = st.slider("Surface", min_surface, max_surface, (min_surface, max_surface))
        
        submit_button = st.form_submit_button(label='🚀 Appliquer les filtres', width="stretch")

# --- INITIALISATION DU SESSION STATE ---
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = df # Au démarrage, on affiche tout

# --- LOGIQUE DE FILTRAGE ---


if submit_button:

    temp_df = df 
    
    if selected_regions:
        temp_df = temp_df[temp_df['Region'].isin(selected_regions)]
    
    if selected_depts:
        temp_df = temp_df[temp_df['Code departement'].isin(selected_depts)]

    if selected_type:
        temp_df = temp_df[temp_df['Type local'].isin(selected_type)]

    if selected_piece:
        temp_df = temp_df[temp_df['Nombre pieces principales'].isin(selected_piece)]
        
    temp_df = temp_df[
        (temp_df['Valeur fonciere'] >= selected_budget[0]) & 
        (temp_df['Valeur fonciere'] <= selected_budget[1])
    ]

    temp_df = temp_df[
        (temp_df['Surface reelle bati'] >= selected_surface[0]) & 
        (temp_df['Surface reelle bati'] <= selected_surface[1])
    ]
    
    st.session_state.filtered_df = temp_df

filtered_df = st.session_state.filtered_df

# --- AFFICHAGE DES RÉSULTATS ---

st.title("🏘️ Analyse du marché de l'immobilier (2024)")
current_year = datetime.datetime.now().year
# KPIs
c1, c2, c3, c4 = st.columns(4)
# 1. Nombre de transactions
nb_ventes = len(filtered_df)
c1.metric("Transactions", f"{nb_ventes:,.0f}".replace(",", " "))
# 2. Prix médian au m²
prix_m2_median = filtered_df['Prix_m2'].median()
c2.metric("Prix médian / m²", f"{prix_m2_median:,.0f} €".replace(",", " "))
# 3. Budget moyen
budget_moyen = filtered_df['Valeur fonciere'].mean()
c3.metric("Budget Moyen", f"{budget_moyen:,.0f} €".replace(",", " "))
# 4. Surface moyenne
surface_moyenne = filtered_df['Surface reelle bati'].mean()
c4.metric("Surface Moyenne", f"{surface_moyenne:.0f} m²")

tab1, tab2, tab3 = st.tabs(["📊 Analyses", "🗺️ Carte", "📋 Données Brutes"])


with tab1:
    # --- PREMIÈRE LIGNE ---
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:

        st.write("### 🏙️ Top 10 des Communes les plus dynamiques (Ventes)")

        total_transactions = len(filtered_df)

        if total_transactions > 0:
            # Prépa des données agrégées
            communes_stats = (
                filtered_df.groupby('Commune')
                .agg(
                    nb_ventes=('Commune', 'size'),        
                    prix_m2_median=('Prix_m2', 'median')  
                )
            )

            # Calculs complémentaires
            # Pourcentage 
            communes_stats['pourcentage'] = (communes_stats['nb_ventes'] / total_transactions) * 100

            # Colonne dédiée à l'affichage textuel
            communes_stats['label_pourcentage'] = communes_stats['pourcentage'].apply(lambda x: f"{x:.1f}%")
            
            # Le top 10 et on nettoie l'index pour Altair
            communes_top10 = communes_stats.sort_values('nb_ventes', ascending=False).head(10).reset_index()

            # Création du graphique Altair 
            base = alt.Chart(communes_top10).encode(
                x=alt.X('Commune:N', sort='-y', title='Commune'), 
                y=alt.Y('nb_ventes:Q', title='Nombre de transactions')
            )

            bars = base.mark_bar(color='#e07a5f').encode(
                tooltip=[
                    alt.Tooltip('Commune:N', title='Commune'),
                    alt.Tooltip('nb_ventes:Q', title='Transactions'),
                    alt.Tooltip('pourcentage:Q', title='Part du marché (%)', format='.1f'),
                    alt.Tooltip('prix_m2_median:Q', title='Prix médian (€/m²)', format=',.0f')
                ]
            )

            # Les étiquettes de pourcentage (au-dessus des barres)
            text = base.mark_text(
                align='center',
                baseline='bottom',
                dy=-5, 
                color='white',
                fontWeight='bold'
            ).encode(
                text=alt.Text('label_pourcentage:N') 
            )

            # Fusion des deux couches
            chart_final = (bars + text).properties(height=400)

            st.altair_chart(chart_final, width="stretch")
            
            if not communes_top10.empty:
                top_commune = communes_top10.iloc[0]
                st.info(f"💡 **{top_commune['Commune'].title()}** est la commune la plus attractive avec **{int(top_commune['nb_ventes'])} ventes**, pour un prix médian de **{int(top_commune['prix_m2_median'])} €/m²**.")

        else:
            st.warning("Aucune donnée disponible pour afficher le palmarès.")

    with row1_col2:
        st.write("### 🏠 Répartition par Type de Bien")

        # Préparation des données 
        df_type = (
            filtered_df.groupby('Type local')
            .size()
            .reset_index(name='Nombre de ventes')
        )

        # Calcul du pourcentage pour le tooltip
        total_ventes = df_type['Nombre de ventes'].sum()

        if total_ventes > 0:
            df_type['pourcentage'] = (df_type['Nombre de ventes'] / total_ventes) * 100
            
            # Définition des couleurs spécifiques
            color_scale = alt.Scale(
                domain=['Appartement', 'Maison'],
                range=['#e07a5f', '#81b29a'] 
            )

            # Création du Camembert avec Altair
            pie_chart = (
                alt.Chart(df_type)
                .mark_arc(innerRadius=75)
                .encode(
                    theta=alt.Theta(field="Nombre de ventes", type="quantitative"),
                    color=alt.Color(field="Type local", type="nominal", scale=color_scale, title="Type de bien"),
                    tooltip=[
                        alt.Tooltip('Type local:N', title="Type de bien"),
                        alt.Tooltip('Nombre de ventes:Q', title="Nombre de ventes", format=",.0f"),
                        alt.Tooltip('pourcentage:Q', title="Part (%)", format=".1f")
                    ]
                )
                .properties(height=350)
            )

            # Affichage sur Streamlit
            st.altair_chart(pie_chart, width="stretch")
            
            dominant = df_type.loc[df_type['Nombre de ventes'].idxmax()]
            st.caption(f"ℹ️ Le marché est dominé par les **{dominant['Type local'].lower()}s** qui représentent {dominant['pourcentage']:.1f}% des transactions.")
            
        else:
            st.warning("Aucune donnée disponible pour cette sélection.")
    
    st.divider()
        
    # --- DEUXIÈME LIGNE ---
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:

        st.write("### 📏 Distribution des Surfaces : Quel est le bien 'type' ?")

        if not filtered_df.empty:

            # les bornes (de 0 jusqu'à la surface max, par pas de 25)
            max_surf = int(filtered_df['Surface reelle bati'].max())
            bins = list(range(0, max_surf + 25, 25))
            
            # étiquettes (ex: "0-25", "25-50")
            labels = [f"{i}-{i+25}" for i in bins[:-1]]
            
            # colonne temporaire avec ces tranches via pd.cut
            df_hist = filtered_df[['Surface reelle bati', 'Type local']]
            df_hist['Tranche'] = pd.cut(df_hist['Surface reelle bati'], bins=bins, labels=labels, right=False)
            
            df_agg = df_hist.groupby(['Tranche', 'Type local'], observed=True).size().reset_index(name='Nombre de ventes')
            df_agg = df_agg[df_agg['Nombre de ventes'] > 0]


            histogram = alt.Chart(df_agg).mark_bar(
                opacity=0.8, 
                cornerRadiusTopLeft=3, 
                cornerRadiusTopRight=3
            ).encode(
                x=alt.X('Tranche:O', 
                        sort=labels, 
                        title='Surface (tranches de 25 m²)'),
                y=alt.Y('Nombre de ventes:Q', 
                        title='Nombre de ventes'),
                color=alt.Color('Type local:N', 
                                scale=alt.Scale(domain=['Appartement', 'Maison'], range=['#e07a5f', '#81b29a']),
                                title='Type de bien'),
                tooltip=[
                    alt.Tooltip('Type local:N', title='Type de bien'),
                    alt.Tooltip('Tranche:O', title='Surface (m²)'),
                    alt.Tooltip('Nombre de ventes:Q', title='Nombre de ventes', format=",.0f")
                ]
            ).properties(
                height=400
            )

            st.altair_chart(histogram, width="stretch")
            surface_mediane = filtered_df['Surface reelle bati'].median()
            
            st.info(f"""
            💡 La moitié des biens vendus dans cette zone font moins de **{surface_mediane:.0f} m²**. 
            """)

        else:
            st.warning("Aucune donnée disponible pour afficher la distribution.")
    
    with row2_col2:

        st.write("### 📈 Évolution temporelle : Le marché est-il en hausse ?")

        if not filtered_df.empty:
            
            # Agrégation : le prix médian au m² pour chaque mois
            evolution_prix = (
                filtered_df.groupby('Mois_Vente')
                .agg(prix_m2_median=('Prix_m2', 'median'))
                .reset_index()
            )

            base_time = alt.Chart(evolution_prix).encode(
                x=alt.X('Mois_Vente:T', title='Date de vente', axis=alt.Axis(format='%b %Y', labelAngle=-45)),
                y=alt.Y('prix_m2_median:Q', title='Prix médian (€/m²)', scale=alt.Scale(zero=False))
            )
            line = base_time.mark_line(color='#e07a5f', strokeWidth=3)
            points = base_time.mark_circle(color='#e07a5f', size=60).encode(
                tooltip=[
                    alt.Tooltip('Mois_Vente:T', title='Mois', format='%B %Y'),
                    alt.Tooltip('prix_m2_median:Q', title='Prix médian (€/m²)', format=',.0f')
                ]
            )

            # Fusion de la ligne et des points
            chart_time = (line + points).properties(height=350)

            st.altair_chart(chart_time, width="stretch")
            
            if len(evolution_prix) >= 2:
                prix_debut = evolution_prix.iloc[0]['prix_m2_median']
                prix_fin = evolution_prix.iloc[-1]['prix_m2_median']
                evolution_pct = ((prix_fin - prix_debut) / prix_debut) * 100
                
                tendance = "en hausse ↗️" if evolution_pct > 0 else "en baisse ↘️"
                
                st.info(f"""
                💡 Sur la période sélectionnée, le marché est **{tendance}** avec une évolution de **{evolution_pct:+.1f}%**. 
                """)

        else:
            st.warning("Aucune donnée disponible pour analyser la tendance temporelle.")
    st.divider()

# --- TROISIEME LIGNE ---
    row3_col1, row3_col2 = st.columns(2)

    with row3_col1:

        st.write("### 💎 La relation Surface / Prix")

        if not filtered_df.empty:
            
            # Échantillonnage pour la performance web
            limite_points = 3000
            if len(filtered_df) > limite_points:
                df_scatter = filtered_df.sample(n=limite_points, random_state=42)
            else:
                df_scatter = filtered_df

            # Création de la base du graphique
            base_scatter = alt.Chart(df_scatter).encode(
                x=alt.X('Surface reelle bati:Q', title='Surface (m²)', scale=alt.Scale(zero=False)),
                y=alt.Y('Prix_m2:Q', title='Prix au m²', scale=alt.Scale(zero=False))
            )

            # Le nuage de points
            points = base_scatter.mark_circle(size=40, opacity=0.4, color='#e07a5f').encode(
                tooltip=[
                    alt.Tooltip('Type local:N', title='Type'),
                    alt.Tooltip('Surface reelle bati:Q', title='Surface (m²)'),
                    alt.Tooltip('Prix_m2:Q', title='Prix (€/m²)', format=',.0f'),
                    alt.Tooltip('Valeur fonciere:Q', title='Prix total (€)', format=',.0f')
                ]
            )

            # La courbe de tendance "LOESS" (Régression locale)
            trend = base_scatter.transform_loess(
                'Surface reelle bati', 'Prix_m2', bandwidth=0.3
            ).mark_line(color='#81b29a', size=4)

            # Fusion des points et de la courbe
            chart_scatter = (points + trend).properties(height=450)

            st.altair_chart(chart_scatter, width="stretch")
            
            st.info("""
            💡En immobilier, plus le bien est petit, plus le prix au mètre carré est élevé. 
            La courbe verte représente la tendance du marché. Au début (petites surfaces), elle chute rapidement. Puis, à partir d'une certaine surface, la décote au mètre carré commence à stagner et la ligne s'aplatit. 
            """)

        else:
            st.warning("Aucune donnée disponible pour analyser la relation surface/prix.")


with tab2:
    col1, col2 = st.columns(2)
    with col2:
        prix_max = st.slider(
            "Plafond de saturation (€/m²)", 
            min_value=2000, max_value=15000, value=10000, step=500,
            help="Les biens plus chers seront affichés avec la couleur maximale."
        )

    df_echantillon = df_carte.copy() 
    df_echantillon['prix_sature'] = df_echantillon['prix_simule_m2'].clip(upper=prix_max)

    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding: 0 10px;">
            <span style="font-size: 14px; font-weight: bold;">0 €/m²</span>
            <div style="flex-grow: 1; height: 15px; background: linear-gradient(to right, rgb(49, 54, 149), rgb(69, 117, 180), rgb(116, 173, 209), rgb(171, 217, 233), rgb(254, 224, 144), rgb(253, 174, 97), rgb(244, 109, 67), rgb(215, 48, 39), rgb(165, 0, 38)); margin: 0 15px; border-radius: 5px;"></div>
            <span style="font-size: 14px; font-weight: bold;">{prix_max} €/m² et +</span>
        </div>
    """, unsafe_allow_html=True)

    carte_pydeck = build_pydeck_map(prix_max, df_carte)
    # Affichage
    st.pydeck_chart(carte_pydeck)


with tab3:
    # données filtrées stockées en session_state
    data_to_show = st.session_state.filtered_df
    section_export(data_to_show)

    st.write(f"### 📋 Données Brutes ({len(data_to_show):,} lignes)")

    st.divider()

    st.write(f"Affichage des {min(100,len(data_to_show)):,} premières lignes :")
    st.dataframe(data_to_show.head(100), width="stretch")


# --- FOOTER / MENTIONS LÉGALES ---
st.divider() 

st.caption("""
**⚠️ Avertissement & Sources :** Ce tableau de bord est un outil interactif de démonstration développé par **Asio Data**. 
Il exploite la base de données ouverte *Demandes de Valeurs Foncières (DVF)* mise à disposition par le gouvernement français sur data.gouv.fr. 
Les analyses, indicateurs et cartographies présentés n'ont qu'une valeur purement indicative. Asio Data ne saurait être tenu responsable de l'utilisation de ce tableau de bord à des fins d'estimation de biens, de conseil financier ou de décision d'investissement immobilier.
""")