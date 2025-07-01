import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

# --- Streamlit Sayfa Ayarları ---
st.set_page_config(
    page_title="Mal Kabul ve Yükleme Takip Sistemi",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS stilleri
st.markdown("""
<style>
    h1 {
        font-size: 24px !important;
        font-weight: 600;
        color: #333333;
        margin-bottom: 18px;
        font-family: 'Segoe UI', sans-serif;
    }
    h3 {
        font-size: 18px !important;
        font-weight: 500;
        color: #333333;
        margin-bottom: 12px;
        font-family: 'Segoe UI', sans-serif;
    }
    .stAlert {
        font-size: 12px !important;
        padding: 8px 16px !important;
    }
    .loading-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: white;
    }
    .active-loading {
        border-left: 4px solid #28a745;
    }
    .completed-loading {
        border-left: 4px solid #6c757d;
    }
    .overdue-loading {
        border-left: 4px solid #dc3545;
    }
    .barcode-input {
        font-size: 18px !important;
        font-weight: bold;
        border: 2px solid #007bff;
        padding: 10px;
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

# --- Yetkili Kullanıcılar ---
AUTHORIZED_USERS = [
    "malkabul@firma.com",
    "yonetici@firma.com",
    "depo@firma.com",
    "admin@firma.com"
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

# --- Kullanıcı Kimlik Doğrulama ---
def authenticate_user():
    if not st.session_state.is_authenticated:
        st.title("🔐 Kullanıcı Girişi")
        st.markdown("### Mal Kabul ve Yükleme Takip Sistemi")
        
        with st.form("login_form"):
            email = st.text_input("📧 E-posta Adresiniz", placeholder="kullanici@firma.com")
            submitted = st.form_submit_button("🚀 Giriş Yap", type="primary")
            
            if submitted:
                if email in AUTHORIZED_USERS:
                    st.session_state.user_email = email
                    st.session_state.is_authenticated = True
                    st.success("✅ Giriş başarılı! Yönlendiriliyorsunuz...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Yetkisiz kullanıcı! Lütfen yetkiniz olan e-posta adresinizi girin.")
        
        st.markdown("---")
        st.info("🔑 **Yetkili Kullanıcılar:** Sistem sadece yetkili e-posta adreslerine sahip kullanıcılar tarafından kullanılabilir.")
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
def filter_operations(df, search_query="", status_filter="Aktif"):
    if df.empty:
        return df
        
    filtered_df = df.copy()
    
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
    
    # Kullanıcı bilgisi
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            label="🔍 Arama (Barkod, Plaka, Şoför, Rampa, Kullanıcı)",
            value=st.session_state.search_query,
            key="search_input",
            placeholder="Aramak için yazın..."
        )
        if search_query != st.session_state.search_query:
            st.session_state.search_query = search_query
            st.rerun()
    
    with col2:
        st.markdown(f"**👤 Kullanıcı:** {st.session_state.user_email}")
        if st.button("🚪 Çıkış Yap"):
            st.session_state.is_authenticated = False
            st.session_state.user_email = ""
            st.rerun()

# --- Sol Kenar Çubuğu ---
def render_sidebar():
    st.sidebar.markdown("### 📋 Menü")
    
    # Tab seçimi
    tab_options = ["Yeni İşlem", "Aktif Yüklemeler", "Tamamlanan İşlemler", "Tüm İşlemler"]
    selected_tab = st.sidebar.selectbox("📂 Bölüm Seçin", tab_options, 
                                       index=tab_options.index(st.session_state.selected_tab))
    
    if selected_tab != st.session_state.selected_tab:
        st.session_state.selected_tab = selected_tab
        st.rerun()
    
    # İstatistikler
    df = load_operations()
    if not df.empty:
        st.sidebar.markdown("### 📊 İstatistikler")
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

# --- Yeni İşlem Formu ---
def render_new_operation_form():
    st.subheader("📦 Yeni Mal Kabul İşlemi")
    
    with st.form("new_operation_form"):
        # Barkod okutma
        st.markdown("### 1️⃣ Barkod Okutma")
        barkod = st.text_input(
            "🏷️ Barkod (İrsaliye Üzerinden)",
            placeholder="Barkodu okutun veya manuel girin...",
            help="Barkod okuyucu ile okutun veya manuel olarak girin"
        )
        
        st.markdown("### 2️⃣ İşlem Bilgileri")
        col1, col2 = st.columns(2)
        
        with col1:
            rampa = st.selectbox("🏗️ Rampa Seçimi *", RAMP_OPTIONS)
            arac_plaka = st.text_input("🚛 Araç Plakası *", placeholder="34 ABC 1234")
        
        with col2:
            sofor = st.text_input("👤 Şoför Adı *", placeholder="Ahmet Yılmaz")
            aciklama = st.text_area("📝 Açıklama", placeholder="Ek bilgiler...")
        
        submitted = st.form_submit_button("🚀 Araç İndirilmeye Başlandı", type="primary")
        
        if submitted:
            if not barkod or not rampa or not arac_plaka or not sofor:
                st.error("⚠️ Lütfen tüm zorunlu alanları doldurunuz!")
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
                baslama_zamani = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
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
                st.cache_data.clear()
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ İşlem kaydedilirken hata: {e}")

# --- Aktif İşlemler Tablosu ---
def render_active_operations():
    st.subheader("🔄 Aktif Yükleme İşlemleri")
    
    df = load_operations()
    active_df = filter_operations(df, st.session_state.search_query, "Aktif")
    
    if active_df.empty:
        st.info("📭 Aktif yükleme işlemi bulunmuyor.")
        return
    
    st.write(f"**Toplam {len(active_df)} aktif işlem**")
    
    for idx, row in active_df.iterrows():
        with st.container():
            # Başlama zamanından geçen süreyi hesapla
            try:
                baslama = datetime.strptime(row["Başlama Zamanı"], "%Y-%m-%d %H:%M:%S")
                gecen_sure = datetime.now() - baslama
                gecen_sure_str = f"{int(gecen_sure.total_seconds() // 60)} dk"
                
                # 2 saatten fazla ise uyarı rengi
                if gecen_sure.total_seconds() > 7200:  # 2 saat = 7200 saniye
                    status_icon = "⚠️"
                    card_class = "overdue-loading"
                else:
                    status_icon = "🔄"
                    card_class = "active-loading"
            except:
                gecen_sure_str = "?"
                status_icon = "🔄"
                card_class = "active-loading"
            
            with st.expander(f"{status_icon} **ID: {row['ID']}** | {row['Rampa']} | {row['Araç Plakası']} | Süre: {gecen_sure_str}", expanded=False):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**🏷️ Barkod:** {row['Barkod']}")
                    st.write(f"**👤 Şoför:** {row['Şoför']}")
                    st.write(f"**⏰ Başlama:** {row['Başlama Zamanı']}")
                
                with col2:
                    st.write(f"**🏗️ Rampa:** {row['Rampa']}")
                    st.write(f"**👨‍💼 İşlem Yapan:** {row['İşlem Yapan']}")
                    if row['Açıklama']:
                        st.write(f"**📝 Açıklama:** {row['Açıklama']}")
                
                with col3:
                    if st.button("✅ Yükleme Bitti", key=f"complete_{row['ID']}_{idx}", type="primary"):
                        complete_loading(row['ID'])
            
            st.divider()

# --- Tamamlanan İşlemler Tablosu ---
def render_completed_operations():
    st.subheader("✅ Tamamlanan İşlemler")
    
    df = load_operations()
    completed_df = filter_operations(df, st.session_state.search_query, "Tamamlandı")
    
    if completed_df.empty:
        st.info("📭 Tamamlanan işlem bulunmuyor.")
        return
    
    st.write(f"**Toplam {len(completed_df)} tamamlanan işlem**")
    
    for idx, row in completed_df.iterrows():
        with st.expander(f"✅ **ID: {row['ID']}** | {row['Rampa']} | {row['Araç Plakası']} | Süre: {row['Süre (dk)']} dk", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**🏷️ Barkod:** {row['Barkod']}")
                st.write(f"**👤 Şoför:** {row['Şoför']}")
                st.write(f"**⏰ Başlama:** {row['Başlama Zamanı']}")
                st.write(f"**🏁 Bitiş:** {row['Bitiş Zamanı']}")
            
            with col2:
                st.write(f"**🏗️ Rampa:** {row['Rampa']}")
                st.write(f"**👨‍💼 İşlem Yapan:** {row['İşlem Yapan']}")
                st.write(f"**⏱️ Toplam Süre:** {row['Süre (dk)']} dakika")
                if row['Açıklama']:
                    st.write(f"**📝 Açıklama:** {row['Açıklama']}")
        
        st.divider()

# --- Tüm İşlemler Tablosu ---
def render_all_operations():
    st.subheader("📋 Tüm İşlemler")
    
    df = load_operations()
    all_df = filter_operations(df, st.session_state.search_query, "Tümü")
    
    if all_df.empty:
        st.info("📭 Kayıtlı işlem bulunmuyor.")
        return
    
    # Özet istatistikler
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔄 Aktif", len(all_df[all_df["Durum"] == "Aktif"]))
    with col2:
        st.metric("✅ Tamamlanan", len(all_df[all_df["Durum"] == "Tamamlandı"]))
    with col3:
        st.metric("📊 Toplam", len(all_df))
    
    # Tablo görünümü
    st.dataframe(
        all_df[["ID", "Barkod", "Rampa", "Araç Plakası", "Şoför", "Başlama Zamanı", "Bitiş Zamanı", "Durum", "Süre (dk)"]],
        use_container_width=True,
        hide_index=True
    )

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
        bitis_zamani = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
    render_sidebar()
    
    # Seçili tab'a göre içerik göster
    if st.session_state.selected_tab == "Yeni İşlem":
        render_new_operation_form()
    elif st.session_state.selected_tab == "Aktif Yüklemeler":
        render_active_operations()
    elif st.session_state.selected_tab == "Tamamlanan İşlemler":
        render_completed_operations()
    elif st.session_state.selected_tab == "Tüm İşlemler":
        render_all_operations()

if __name__ == "__main__":
    main()