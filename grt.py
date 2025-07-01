import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import hashlib
import uuid
import re

def get_local_time():
    """Türkiye saatine göre yerel zaman döndürür"""
    tz = pytz.timezone("Europe/Istanbul")
    return datetime.now(tz)

# --- Streamlit Sayfa Ayarları ---
st.set_page_config(
    page_title="Mal Kabul ve Yükleme Takip Sistemi",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS stilleri - Mobile optimized
st.markdown("""
<style>
    /* Genel stil ayarları */
    h1 {
        font-size: 22px !important;
        font-weight: 600;
        color: #333333;
        margin-bottom: 15px;
        font-family: 'Segoe UI', sans-serif;
    }
    h3 {
        font-size: 18px !important;
        font-weight: 500;
        color: #333333;
        margin-bottom: 12px;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Mobile optimized buttons */
    .action-buttons {
        margin: 15px 0;
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }
    
    .action-button {
        flex: 1;
        min-width: 140px;
        padding: 12px 16px;
        background: linear-gradient(135deg, #007bff, #0056b3);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        text-align: center;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,123,255,0.2);
    }
    
    .action-button:hover {
        background: linear-gradient(135deg, #0056b3, #003d82);
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,123,255,0.3);
    }
    
    .action-button.success {
        background: linear-gradient(135deg, #28a745, #1e7e34);
    }
    
    .action-button.success:hover {
        background: linear-gradient(135deg, #1e7e34, #155724);
    }
    
    /* Logout button styling */
    .logout-btn {
        background: #dc3545;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
        margin-left: 10px;
    }
    
    /* Loading cards */
    .loading-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
        background-color: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .active-loading {
        border-left: 5px solid #28a745;
        background: linear-gradient(135deg, #f8fff9, #ffffff);
    }
    
    .completed-loading {
        border-left: 5px solid #6c757d;
        background: linear-gradient(135deg, #f8f9fa, #ffffff);
    }
    
    .overdue-loading {
        border-left: 5px solid #dc3545;
        background: linear-gradient(135deg, #fff5f5, #ffffff);
    }
    
    /* Form styling */
    .stForm {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin: 15px 0;
    }
    
    /* Alert styling */
    .stAlert {
        font-size: 14px !important;
        padding: 12px 16px !important;
        border-radius: 8px !important;
        margin: 10px 0 !important;
    }
    
    /* Input styling */
    .stTextInput > div > div > input {
        font-size: 16px !important;
        padding: 12px !important;
        border-radius: 8px !important;
    }
    
    /* Date picker container */
    .date-filter-container {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin: 15px 0;
        border: 1px solid #e9ecef;
    }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        .action-buttons {
            flex-direction: column;
        }
        
        .action-button {
            width: 100%;
            min-width: unset;
            margin-bottom: 8px;
        }
        
        h1 {
            font-size: 20px !important;
        }
        
        .loading-card {
            padding: 12px;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- Session State Başlatma ---
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = 'Yeni İşlem'
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'is_authenticated' not in st.session_state:
    st.session_state.is_authenticated = False
if 'user_token' not in st.session_state:
    st.session_state.user_token = ""
if 'date_filter' not in st.session_state:
    st.session_state.date_filter = None
if 'remember_me' not in st.session_state:
    st.session_state.remember_me = False

# --- Yetkili Kullanıcılar ---
AUTHORIZED_USERS = [
    "muhammed@norm.com",
    "umit@norm.com",
    "tevfik@norm.com",
    "fatih@norm.com",
    "murat@norm.com",
    "goksel@norm.com",
    "samet@norm.com",
    "erhan@norm.com",
    "salih@norm.com",
    "coskun@norm.com",
    "zeynal@norm.com",
    "serkan@norm.com",
    "huseyin@norm.com"
]

# --- Rampa Seçenekleri ---
RAMP_OPTIONS = ["Kuzey Rampa", "Güney Rampa", "Yer Rampası"]

# --- Google Sheets Yetkilendirme ---
try:
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=credentials)
    SHEET_ID = st.secrets["spreadsheet"]["id"]
except:
    st.error("Google Sheets bağlantısı kurulamadı. Lütfen ayarları kontrol edin.")
    st.stop()

SHEET_NAME = "LoadingOperations"

# --- Güvenlik Fonksiyonları ---
def generate_user_token(email):
    """Kullanıcı için benzersiz token oluştur"""
    timestamp = str(int(time.time()))
    unique_string = f"{email}_{timestamp}_{uuid.uuid4()}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:32]

def check_url_token():
    """URL'den token kontrolü yap"""
    query_params = st.query_params
    if 'token' in query_params and 'email' in query_params:
        token = query_params['token'][0]
        email = query_params['email'][0]
        
        if email in AUTHORIZED_USERS:
            st.session_state.user_email = email
            st.session_state.user_token = token
            st.session_state.is_authenticated = True
            st.session_state.remember_me = True
            return True
    return False

def create_remember_link(email, token):
    """Hatırla bağlantısı oluştur"""
    base_url = "https://your-app-url.streamlit.app"  # Gerçek URL'nizi buraya yazın
    return f"{base_url}?email={email}&token={token}"

# --- Kullanıcı Kimlik Doğrulama ---
def authenticate_user():
    # URL token kontrolü
    if not st.session_state.is_authenticated:
        if check_url_token():
            st.rerun
        
        else:
            # Otomatik giriş için token kontrolü
            if st.session_state.remember_me and st.session_state.user_email and st.session_state.user_token:
                if st.session_state.user_email in AUTHORIZED_USERS:
                    st.session_state.is_authenticated = True
                    st.rerun()        
    
    if not st.session_state.is_authenticated:
        st.markdown("""
        <div style="text-align: center; padding: 20px;">
            <h1>🔐 Mal Kabul ve Yükleme Takip Sistemi</h1>
            <p style="font-size: 16px; color: #666;">Güvenli giriş yapın</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.container():
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                with st.form("login_form"):
                    st.markdown("### 👤 Giriş Bilgileri")
                    email = st.text_input(
                        "📧 E-posta Adresiniz", 
                        placeholder="ad@firma.com",
                        help="Yetkili e-posta adresinizi girin"
                    )
                    
                    remember_me = st.checkbox(
                        "🔒 Beni hatırla (Bu cihazda oturum açık kalsın)",
                        value=True,
                        help="İşaretlerseniz, bir sonraki girişinizde otomatik giriş yaparsınız"
                    )
                    
                    submitted = st.form_submit_button("🚀 Giriş Yap", type="primary", use_container_width=True)
                    
                    if submitted:
                        if email in AUTHORIZED_USERS:
                            st.session_state.user_email = email
                            st.session_state.is_authenticated = True
                            st.session_state.remember_me = remember_me
                            
                            if remember_me:
                                # Token oluştur ve göster
                                token = generate_user_token(email)
                                st.session_state.user_token = token
                                remember_link = create_remember_link(email, token)
                                
                                st.success("✅ Giriş başarılı!")
                                st.info("🔖 **Önemli:** Aşağıdaki bağlantıyı kaydedin. Bu bağlantı ile bir sonraki sefer direkt giriş yapabilirsiniz.")
                                st.code(remember_link)
                                st.markdown("📱 **Mobil kullanım için:** Bu bağlantıyı telefonunuzun ana ekranına kısayol olarak ekleyebilirsiniz.")
                            else:
                                st.success("✅ Giriş başarılı! Yönlendiriliyorsunuz...")
                            
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Yetkisiz kullanıcı! Lütfen yetkiniz olan e-posta adresinizi girin.")
        
        with st.expander("ℹ️ Giriş Hakkında Bilgi", expanded=False):
            st.markdown("""
            **Yetkili Kullanıcılar:**
            - Mal kabul personeli
            - Saha ve Takım Liderleri 
            - Yöneticiler
            
            **Güvenlik:**
            - Sadece yetkili e-posta adresleri kabul edilir
            - "Beni hatırla" seçeneği ile kolay erişim
            - Güvenli token tabanlı oturum yönetimi
            
            **Mobil Kullanım:**
            - Telefon tarayıcınızda sorunsuz çalışır
            - Ana ekrana kısayol ekleyebilirsiniz
            """)
        
        return False
    return True

# --- Google Sheets Fonksiyonları ---
def read_sheet(range_):
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=range_
        ).execute()
        values = result.get("values", [])
        if not values:
            return pd.DataFrame()
        
        headers = values[0] if values else []
        data_rows = values[1:] if len(values) > 1 else []
        
        if not data_rows:
            return pd.DataFrame(columns=headers if headers else get_required_columns())
        
        max_cols = len(headers) if headers else len(get_required_columns())
        normalized_rows = []
        for row in data_rows:
            normalized_row = row[:]
            while len(normalized_row) < max_cols:
                normalized_row.append("")
            normalized_row = normalized_row[:max_cols]
            normalized_rows.append(normalized_row)
        
        if headers:
            df = pd.DataFrame(normalized_rows, columns=headers)
        else:
            df = pd.DataFrame(normalized_rows, columns=get_required_columns())
        
        return df
        
    except Exception as e:
        st.error(f"Google Sheets'ten okunamadı: {e}")
        return pd.DataFrame()

def get_required_columns():
    return [
        "ID", "Barkod", "Rampa", "Araç Plakası", "Şoför", "Açıklama", 
        "Başlama Zamanı", "Bitiş Zamanı", "Durum", "İşlem Yapan", "Süre (dk)"
    ]

def write_sheet(range_name, values):
    try:
        clean_values = []
        for row in values:
            clean_row = []
            for cell in row:
                if pd.isna(cell) or cell == 'NaN' or str(cell) == 'nan':
                    clean_row.append("")
                else:
                    clean_row.append(str(cell))
            clean_values.append(clean_row)
        
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": clean_values}
        ).execute()
    except Exception as e:
        st.error(f"Google Sheets'e yazılamadı: {e}")
        raise

def save_operations_to_sheet(df):
    """DataFrame'i Google Sheets'e güvenli şekilde kaydeder"""
    try:
        df_clean = df.fillna("")
        
        # Tüm sheet'i temizle
        service.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A1:Z1000"
        ).execute()
        
        # Yeni veriyi yaz
        values = [df_clean.columns.tolist()] + df_clean.values.tolist()
        write_sheet(f"{SHEET_NAME}!A1", values)
        
    except Exception as e:
        st.error(f"Veri kaydedilirken hata: {e}")
        raise

@st.cache_data(ttl=30)
def load_operations():
    df = read_sheet(f"{SHEET_NAME}!A1:Z1000")
    required_columns = get_required_columns()
    
    if df.empty:
        df = pd.DataFrame(columns=required_columns)
    else:
        for col in required_columns:
            if col not in df.columns:
                df[col] = ""
        df = df[required_columns]
        df = df.fillna("")
        
        # ID'leri kontrol et, boşsa yeni ID ata
        if 'ID' in df.columns:
            df['ID'] = df['ID'].replace("", pd.NA)
            empty_ids = df['ID'].isna()
            if empty_ids.any():
                max_id = 0
                for id_val in df['ID'].dropna():
                    try:
                        max_id = max(max_id, int(str(id_val)))
                    except:
                        pass
                
                new_ids = range(max_id + 1, max_id + 1 + empty_ids.sum())
                df.loc[empty_ids, 'ID'] = [str(i) for i in new_ids]
    
    return df

# --- Filtre Fonksiyonları ---
def filter_operations(df, search_query="", status_filter="Aktif", date_filter=None):
    if df.empty:
        return df
        
    filtered_df = df.copy()
    
    # Tarih filtresi (yeni)
    if date_filter:
        try:
            filter_date = date_filter.strftime("%Y-%m-%d")
            filtered_df['Başlama_Date'] = pd.to_datetime(filtered_df['Başlama Zamanı'], errors='coerce').dt.strftime("%Y-%m-%d")
            filtered_df = filtered_df[filtered_df['Başlama_Date'] == filter_date]
            filtered_df = filtered_df.drop('Başlama_Date', axis=1)
        except:
            pass
    
    # Durum filtresi
    if status_filter != "Tümü":
        filtered_df = filtered_df[filtered_df["Durum"] == status_filter]
    
    # Arama filtresi
    if search_query:
        mask = (
            filtered_df["Barkod"].str.contains(search_query, case=False, na=False) |
            filtered_df["Araç Plakası"].str.contains(search_query, case=False, na=False) |
            filtered_df["Şoför"].str.contains(search_query, case=False, na=False) |
            filtered_df["Rampa"].str.contains(search_query, case=False, na=False) |
            filtered_df["İşlem Yapan"].str.contains(search_query, case=False, na=False) |
            filtered_df["Açıklama"].str.contains(search_query, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    # Tarihe göre sırala (en yeni önce)
    try:
        if not filtered_df.empty and "Başlama Zamanı" in filtered_df.columns:
            filtered_df_sorted = filtered_df.copy()
            filtered_df_sorted['Başlama_DateTime'] = pd.to_datetime(filtered_df_sorted['Başlama Zamanı'], errors='coerce')
            filtered_df_sorted = filtered_df_sorted.sort_values('Başlama_DateTime', ascending=False)
            filtered_df = filtered_df_sorted.drop('Başlama_DateTime', axis=1)
    except:
        pass

    return filtered_df

# --- Üst Menü ---
def render_header():
    st.title("🚛 Mal Kabul ve Yükleme Takip Sistemi")
    
    # Sadece arama çubuğu kalsın
    search_query = st.text_input(
        label="🔍 Arama (Barkod, Plaka, Şoför, Rampa, Kullanıcı)",
        value=st.session_state.search_query,
        key="search_input",
        placeholder="Aramak için yazın...",
        help="Tüm alanlarda arama yapar"
    )
    if search_query != st.session_state.search_query:
        st.session_state.search_query = search_query
        st.rerun()
    
# --- Ana Butonlar (Mobile Optimized) ---
def render_action_buttons():
    st.markdown("""
    <div class="action-buttons">
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📦 Yeni İşlem", key="btn_new", type="primary", use_container_width=True):
            st.session_state.selected_tab = 'Yeni İşlem'
            st.rerun()
    
    with col2:
        df = load_operations()
        aktif_count = len(df[df["Durum"] == "Aktif"]) if not df.empty else 0
        if st.button(f"🔄 Aktif Yüklemeler ({aktif_count})", key="btn_active", use_container_width=True):
            st.session_state.selected_tab = 'Aktif Yüklemeler'
            st.rerun()
    
    with col3:
        if st.button("📋 Tüm İşlemler", key="btn_all", use_container_width=True):
            st.session_state.selected_tab = 'Tüm İşlemler'
            st.rerun()

    # Aktif filtre göstergesi
    if st.session_state.date_filter:
        st.info(f"📅 **Tarih Filtresi Aktif:** {st.session_state.date_filter.strftime('%d.%m.%Y')}")

# --- Sol Kenar Çubuğu ---
def render_sidebar():
    # Kullanıcı bilgisi ve çıkış
    st.sidebar.markdown(f"### 👤 {st.session_state.user_email.split('@')[0]}")
    if st.sidebar.button("🚪 Çıkış Yap", key="sidebar_logout", use_container_width=True):
        st.session_state.is_authenticated = False
        st.session_state.user_email = ""
        st.session_state.user_token = ""
        st.session_state.remember_me = False
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Navigasyon pop-up
    st.sidebar.markdown("### 📋 Navigasyon")
    
    with st.sidebar.expander("🔍 Filtreler", expanded=False):
        # Tarih filtresi
        date_filter = st.date_input(
            "📅 Tarih Filtresi",
            value=st.session_state.date_filter,
            help="Belirli bir günün işlemlerini görmek için tarih seçin",
            key="sidebar_date_filter"
        )
        
        if date_filter != st.session_state.date_filter:
            st.session_state.date_filter = date_filter
            st.rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗓️ Bugün", key="sidebar_today_filter", use_container_width=True):
                st.session_state.date_filter = get_local_time().date()
                st.rerun()
        
        with col2:
            if st.button("🔄 Temizle", key="sidebar_clear_filter", use_container_width=True):
                st.session_state.date_filter = None
                st.rerun()
        
        # Aktif filtre göstergesi
        if st.session_state.date_filter:
            st.info(f"📅 **Aktif:** {st.session_state.date_filter.strftime('%d.%m.%Y')}")
    
    # Mevcut tab göstergesi
    current_tab = st.session_state.selected_tab
    st.sidebar.info(f"📍 **Aktif Bölüm:** {current_tab}")
    
    # İstatistikler
    df = load_operations()
    if not df.empty:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 Genel İstatistikler")
        
        aktif_count = len(df[df["Durum"] == "Aktif"])
        tamamlanan_count = len(df[df["Durum"] == "Tamamlandı"])
        
        st.sidebar.metric("🔄 Aktif İşlemler", aktif_count)
        st.sidebar.metric("✅ Tamamlanan İşlemler", tamamlanan_count)
        st.sidebar.metric("📈 Toplam İşlemler", len(df))
        
        # Rampa dağılımı
        if "Rampa" in df.columns:
            st.sidebar.markdown("### 🏗️ Rampa Dağılımı")
            rampa_counts = df["Rampa"].value_counts()
            for rampa, count in rampa_counts.items():
                if rampa:  # Boş olmayan rampa değerleri
                    st.sidebar.write(f"**{rampa}:** {count}")
        
        # Bugünkü özet
        try:
            today = get_local_time().date()
            df['Başlama_Date'] = pd.to_datetime(df['Başlama Zamanı'], errors='coerce').dt.date
            today_df = df[df['Başlama_Date'] == today]
            
            if not today_df.empty:
                st.sidebar.markdown("---")
                st.sidebar.markdown("### 📅 Bugünkü Özet")
                st.sidebar.metric("Bugün Başlanan", len(today_df))
                st.sidebar.metric("Bugün Tamamlanan", len(today_df[today_df["Durum"] == "Tamamlandı"]))
        except:
            pass
    
    # Sistem bilgileri
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ Sistem Bilgisi")
    st.sidebar.write(f"**Son Güncelleme:** {get_local_time().strftime('%H:%M')}")
    
    if st.session_state.remember_me:
        st.sidebar.success("🔒 Oturum hatırlanıyor")
    
    # Yardım
    with st.sidebar.expander("❓ Yardım"):
        st.markdown("""
        **Hızlı Kısayollar:**
        - 📦 Yeni işlem başlat
        - 🔄 Aktif yüklemeleri gör
        - 📅 Tarih filtresi kullan
        
        **Mobil İpuçları:**
        - Ana ekrana kısayol ekle
        - Yatay modda kullan
        - Barkod okuyucu kullan
        """)

# --- Yeni İşlem Formu ---
def render_new_operation_form():
    st.subheader("📦 Yeni Mal Kabul İşlemi")
    
    with st.form("new_operation_form"):
        # Barkod okutma
        st.markdown("### 1️⃣ Barkod Okutma")
        barkod = st.text_input(
            "🏷️ Teslimat No (İrsaliye Üzerinden)",
            placeholder="10 haneli barkodu girin",
            help="Manuel olarak girin"
        )
        
        st.markdown("### 2️⃣ İşlem Bilgileri")
        col1, col2 = st.columns(2)
        
        with col1:
            rampa = st.selectbox("🏗️ Rampa Seçimi *", RAMP_OPTIONS)
            arac_plaka = st.text_input("🚛 Araç Plakası *", placeholder="34 ABC 1234")
        
        with col2:
            sofor = st.text_input("👤 Şoför Adı *", placeholder="Ahmet Yılmaz")
            aciklama = st.text_area("📝 Açıklama", placeholder="Ek bilgiler...")
        
        submitted = st.form_submit_button("🚀 Araç İndirilmeye Başlandı", type="primary", use_container_width=True)
        
        if submitted:
            if not barkod or not rampa or not arac_plaka or not sofor:
                st.error("⚠️ Lütfen tüm zorunlu alanları doldurunuz!")
                return
            
            # 🔐 Barkod 10 haneli sayı mı kontrol et
            if not re.fullmatch(r"\d{10}", barkod):
                st.error("❌ Barkod yalnızca 10 haneli sayı olmalıdır!")
                return
            
            try:
                df = load_operations()
                
                # Yeni ID oluştur
                if df.empty:
                    new_id = "1"
                else:
                    max_id = 0
                    for id_val in df['ID']:
                        try:
                            max_id = max(max_id, int(str(id_val)))
                        except:
                            pass
                    new_id = str(max_id + 1)
                
                # Yeni işlem kaydı
                baslama_zamani = get_local_time().strftime("%Y-%m-%d %H:%M:%S")
                
                yeni_islem = {
                    "ID": new_id,
                    "Barkod": barkod,
                    "Rampa": rampa,
                    "Araç Plakası": arac_plaka.upper(),
                    "Şoför": sofor,
                    "Açıklama": aciklama,
                    "Başlama Zamanı": baslama_zamani,
                    "Bitiş Zamanı": "",
                    "Durum": "Aktif",
                    "İşlem Yapan": st.session_state.user_email,
                    "Süre (dk)": ""
                }
                
                new_df = pd.concat([df, pd.DataFrame([yeni_islem])], ignore_index=True)
                save_operations_to_sheet(new_df)
                
                st.success(f"✅ Yeni işlem başlatıldı! **ID: {new_id}** | **Rampa: {rampa}** | **Plaka: {arac_plaka.upper()}**")
                st.balloons()  # Kutlama efekti
                st.cache_data.clear()
                
                # Aktif yüklemeler sayfasına yönlendir
                time.sleep(2)
                st.session_state.selected_tab = 'Aktif Yüklemeler'
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ İşlem kaydedilirken hata: {e}")

# --- Aktif İşlemler Tablosu ---
def render_active_operations():
    st.subheader("🔄 Aktif Yükleme İşlemleri")
    
    df = load_operations()
    active_df = filter_operations(df, st.session_state.search_query, "Aktif", st.session_state.date_filter)
    
    if active_df.empty:
        st.info("📭 Aktif yükleme işlemi bulunmuyor.")
        
        # Yeni işlem başlatma öneri butonu
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📦 Yeni İşlem Başlat", type="primary", use_container_width=True):
                st.session_state.selected_tab = 'Yeni İşlem'
                st.rerun()
        return
    
    st.write(f"**Toplam {len(active_df)} aktif işlem**")
    
    # Sıralama seçenekleri
    col1, col2 = st.columns([3, 1])
    with col2:
        sort_option = st.selectbox(
            "Sıralama:",
            ["En Yeni", "En Eski", "Rampa", "Plaka"],
            key="active_sort"
        )
    
    # Sıralama uygula
    if sort_option == "En Eski":
        try:
            active_df['Başlama_DateTime'] = pd.to_datetime(active_df['Başlama Zamanı'], errors='coerce')
            active_df = active_df.sort_values('Başlama_DateTime', ascending=True)
            active_df = active_df.drop('Başlama_DateTime', axis=1)
        except:
            pass
    elif sort_option == "Rampa":
        active_df = active_df.sort_values('Rampa', ascending=True)
    elif sort_option == "Plaka":
        active_df = active_df.sort_values('Araç Plakası', ascending=True)
    
    for idx, row in active_df.iterrows():
        with st.container():
            # Başlama zamanından geçen süreyi hesapla
            try:
                tz = pytz.timezone("Europe/Istanbul")
                baslama = tz.localize(datetime.strptime(row["Başlama Zamanı"], "%Y-%m-%d %H:%M:%S"))
                gecen_sure = get_local_time() - baslama
                gecen_sure_dk = int(gecen_sure.total_seconds() // 60)
                gecen_sure_str = f"{gecen_sure_dk} dk"
                
                # Süre bazlı renk kodlaması
                if gecen_sure.total_seconds() > 7200:  # 2 saat
                    status_icon = "⚠️"
                    card_class = "overdue-loading"
                    time_color = "#dc3545"
                elif gecen_sure.total_seconds() > 3600:  # 1 saat
                    status_icon = "🕐"
                    card_class = "active-loading"
                    time_color = "#ffc107"
                else:
                    status_icon = "🔄"
                    card_class = "active-loading"
                    time_color = "#28a745"
            except:
                gecen_sure_str = "?"
                status_icon = "🔄"
                card_class = "active-loading"
                time_color = "#6c757d"
            
            with st.expander(
                f"{status_icon} **ID: {row['ID']}** | {row['Rampa']} | {row['Araç Plakası']} | Süre: {gecen_sure_str}", 
                expanded=False
            ):
                # İşlem detayları
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**🏷️ Barkod:** `{row['Barkod']}`")
                    st.markdown(f"**👤 Şoför:** {row['Şoför']}")
                    st.markdown(f"**⏰ Başlama:** {row['Başlama Zamanı']}")
                
                with col2:
                    st.markdown(f"**🏗️ Rampa:** {row['Rampa']}")
                    st.markdown(f"**👨‍💼 İşlem Yapan:** {row['İşlem Yapan'].split('@')[0]}")
                    if row['Açıklama']:
                        st.markdown(f"**📝 Açıklama:** {row['Açıklama']}")
                
                with col3:
                    # Büyük tamamlama butonu
                    if st.button(
                        "✅ Yükleme Bitti", 
                        key=f"complete_{row['ID']}_{idx}", 
                        type="primary",
                        use_container_width=True,
                        help=f"ID {row['ID']} işlemini tamamla"
                    ):
                        complete_loading(row['ID'])
                    
                    # Geçen süre göstergesi
                    st.markdown(f"""
                    <div style="text-align: center; margin-top: 10px;">
                        <span style="color: {time_color}; font-weight: bold; font-size: 14px;">
                            ⏱️ {gecen_sure_str}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.divider()

# --- Tamamlanan İşlemler Tablosu ---
def render_completed_operations():
    st.subheader("✅ Tamamlanan İşlemler")
    
    df = load_operations()
    completed_df = filter_operations(df, st.session_state.search_query, "Tamamlandı", st.session_state.date_filter)
    
    if completed_df.empty:
        st.info("📭 Tamamlanan işlem bulunmuyor.")
        return
    
    st.write(f"**Toplam {len(completed_df)} tamamlanan işlem**")
    
    # Ortalama süre hesaplama
    try:
        sure_values = []
        for sure_str in completed_df['Süre (dk)']:
            try:
                if sure_str and str(sure_str).strip():
                    sure_values.append(float(sure_str))
            except:
                continue
        
        if sure_values:
            avg_time = sum(sure_values) / len(sure_values)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("⏱️ Ortalama Süre", f"{avg_time:.0f} dk")
            with col2:
                st.metric("🏃 En Hızlı", f"{min(sure_values):.0f} dk")
            with col3:
                st.metric("🐌 En Yavaş", f"{max(sure_values):.0f} dk")
    except:
        pass
    
    for idx, row in completed_df.iterrows():
        with st.expander(
            f"✅ **ID: {row['ID']}** | {row['Rampa']} | {row['Araç Plakası']} | Süre: {row['Süre (dk)']} dk", 
            expanded=False
        ):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**🏷️ Barkod:** `{row['Barkod']}`")
                st.markdown(f"**👤 Şoför:** {row['Şoför']}")
                st.markdown(f"**⏰ Başlama:** {row['Başlama Zamanı']}")
                st.markdown(f"**🏁 Bitiş:** {row['Bitiş Zamanı']}")
            
            with col2:
                st.markdown(f"**🏗️ Rampa:** {row['Rampa']}")
                st.markdown(f"**👨‍💼 İşlem Yapan:** {row['İşlem Yapan'].split('@')[0]}")
                st.markdown(f"**⏱️ Toplam Süre:** {row['Süre (dk)']} dakika")
                if row['Açıklama']:
                    st.markdown(f"**📝 Açıklama:** {row['Açıklama']}")
        
        st.divider()

# --- Tüm İşlemler Tablosu ---
def render_all_operations():
    st.subheader("📋 Tüm İşlemler")
    
    df = load_operations()
    all_df = filter_operations(df, st.session_state.search_query, "Tümü", st.session_state.date_filter)
    
    if all_df.empty:
        st.info("📭 Kayıtlı işlem bulunmuyor.")
        return
    
    # Görünüm seçenekleri
    col1, col2 = st.columns([3, 1])
    with col1:
        view_mode = st.selectbox(
            "Görünüm:",
            ["Kart Görünümü", "Tablo Görünümü"],
            key="view_mode"
        )
    with col2:
        show_count = st.selectbox(
            "Göster:",
            [50, 100, 200, "Tümü"],
            key="show_count"
        )
    
    # Kayıt sayısını sınırla
    if show_count != "Tümü":
        display_df = all_df.head(show_count)
    else:
        display_df = all_df
    
    if view_mode == "Tablo Görünümü":
        # Tablo görünümü
        st.dataframe(
            display_df[["ID", "Barkod", "Rampa", "Araç Plakası", "Şoför", "Başlama Zamanı", "Bitiş Zamanı", "Durum", "Süre (dk)"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Barkod": st.column_config.TextColumn("Barkod", width="medium"),
                "Rampa": st.column_config.TextColumn("Rampa", width="medium"),
                "Araç Plakası": st.column_config.TextColumn("Plaka", width="medium"),
                "Şoför": st.column_config.TextColumn("Şoför", width="medium"),
                "Başlama Zamanı": st.column_config.DatetimeColumn("Başlama", width="medium"),
                "Bitiş Zamanı": st.column_config.DatetimeColumn("Bitiş", width="medium"),
                "Durum": st.column_config.TextColumn("Durum", width="small"),
                "Süre (dk)": st.column_config.NumberColumn("Süre", width="small")
            }
        )
    else:
        # Kart görünümü
        for idx, row in display_df.iterrows():
            status_icon = "🔄" if row["Durum"] == "Aktif" else "✅"
            card_class = "active-loading" if row["Durum"] == "Aktif" else "completed-loading"
            
            with st.expander(
                f"{status_icon} **ID: {row['ID']}** | {row['Rampa']} | {row['Araç Plakası']} | {row['Durum']}", 
                expanded=False
            ):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**🏷️ Barkod:** `{row['Barkod']}`")
                    st.markdown(f"**👤 Şoför:** {row['Şoför']}")
                    st.markdown(f"**⏰ Başlama:** {row['Başlama Zamanı']}")
                    if row['Bitiş Zamanı']:
                        st.markdown(f"**🏁 Bitiş:** {row['Bitiş Zamanı']}")
                
                with col2:
                    st.markdown(f"**🏗️ Rampa:** {row['Rampa']}")
                    st.markdown(f"**👨‍💼 İşlem Yapan:** {row['İşlem Yapan'].split('@')[0]}")
                    if row['Süre (dk)']:
                        st.markdown(f"**⏱️ Süre:** {row['Süre (dk)']} dakika")
                    if row['Açıklama']:
                        st.markdown(f"**📝 Açıklama:** {row['Açıklama']}")
                
                with col3:
                    # Durum göstergesi
                    if row["Durum"] == "Aktif":
                        if st.button(
                            "✅ Tamamla", 
                            key=f"complete_all_{row['ID']}_{idx}", 
                            type="primary",
                            use_container_width=True
                        ):
                            complete_loading(row['ID'])
                    else:
                        st.success("Tamamlandı")
            
            st.divider()
    
    # Sayfa altında özet
    if len(all_df) > len(display_df):
        st.info(f"📊 Toplam {len(all_df)} işlemden {len(display_df)} tanesi gösteriliyor.")

# --- İşlem Tamamlama ---
def complete_loading(operation_id):
    """Yükleme işlemini tamamla"""
    try:
        st.cache_data.clear()
        df = load_operations()
        
        # ID ile eşleşen satırı bul
        operation_mask = df["ID"] == str(operation_id)
        matching_operations = df[operation_mask]
        
        if matching_operations.empty:
            st.error(f"❌ ID {operation_id} bulunamadı!")
            return
        
        if len(matching_operations) > 1:
            st.error(f"❌ ID {operation_id} için birden fazla kayıt bulundu!")
            return
        
        # İşlemi tamamla
        bitis_zamani = get_local_time().strftime("%Y-%m-%d %H:%M:%S")
        
        # Süre hesapla
        try:
            baslama = datetime.strptime(matching_operations.iloc[0]["Başlama Zamanı"], "%Y-%m-%d %H:%M:%S")
            bitis = datetime.strptime(bitis_zamani, "%Y-%m-%d %H:%M:%S")
            sure_dk = int((bitis - baslama).total_seconds() // 60)
        except:
            sure_dk = 0
        
        df.loc[operation_mask, "Durum"] = "Tamamlandı"
        df.loc[operation_mask, "Bitiş Zamanı"] = bitis_zamani
        df.loc[operation_mask, "Süre (dk)"] = str(sure_dk)
        
        save_operations_to_sheet(df)
        
        st.success(f"✅ İşlem tamamlandı! **ID: {operation_id}** | **Süre: {sure_dk} dakika**")
        st.balloons()  # Kutlama efekti
        st.cache_data.clear()
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ İşlem tamamlanırken hata: {e}")

# --- Ana Uygulama ---
def main():
    # Kimlik doğrulama kontrolü
    if not authenticate_user():
        return
    
    # Ana uygulama
    render_header()
    
    # Ana butonlar (mobil optimized)
    render_action_buttons()
      
    # Sidebar
    render_sidebar()
    
    # İçerik separator
    st.markdown("---")
    
    # Seçili tab'a göre içerik göster
    if st.session_state.selected_tab == "Yeni İşlem":
        render_new_operation_form()
    elif st.session_state.selected_tab == "Aktif Yüklemeler":
        render_active_operations()
    elif st.session_state.selected_tab == "Tamamlanan İşlemler":
        render_completed_operations()
    elif st.session_state.selected_tab == "Tüm İşlemler":
        render_all_operations()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 12px; padding: 20px;">
        🚛 Mal Kabul ve Yükleme Takip Sistemi | 
        📱 Mobil Optimized | 
        🔒 Güvenli Oturum Yönetimi
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()