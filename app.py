import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io
import re

from google import genai
from dotenv import load_dotenv


# =====================================================
# 1. PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="APBD Analytics AI",
    page_icon="📊",
    layout="wide"
)


# =====================================================
# 2. LOAD GEMINI API KEY
# =====================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    if "GEMINI_API_KEY" in st.secrets:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass


# =====================================================
# 3. INITIALIZE GEMINI
# =====================================================

client = None

if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        client = None

MODEL_NAME = "gemini-2.5-flash"


# =====================================================
# 4. HELPER FUNCTIONS
# =====================================================

def format_rupiah(value):
    """Format angka dalam Rupiah."""
    return "Rp " + f"{value:,.0f}".replace(",", ".")


def parse_number(value):
    """
    Mengubah angka dari format Indonesia maupun internasional.
    Contoh:
    1.250.000
    1.250.000,50
    1250000.50
    """

    if pd.isna(value):
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    text = text.replace("Rp", "")
    text = text.replace("%", "")
    text = text.replace(" ", "")

    # Format Indonesia: 1.250.000,50
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    # Format Indonesia: 1.250.000
    elif "," in text:
        text = text.replace(",", ".")

    # Format angka dengan pemisah ribuan
    elif text.count(".") > 1:
        text = text.replace(".", "")

    # Format seperti 1.250 dianggap ribuan
    elif "." in text:
        parts = text.split(".")

        if len(parts[-1]) == 3:
            text = text.replace(".", "")

    text = re.sub(r"[^0-9.-]", "", text)

    try:
        return float(text)
    except Exception:
        return 0.0


def find_column(columns, keywords):
    """Mencari kolom berdasarkan kata kunci."""

    for column in columns:
        name = str(column).lower().strip()

        for keyword in keywords:
            if keyword in name:
                return column

    return columns[0]


def read_uploaded_file(uploaded_file):
    """Membaca file Excel atau CSV."""

    extension = uploaded_file.name.lower()

    if extension.endswith(".xlsx") or extension.endswith(".xls"):
        return pd.read_excel(uploaded_file)

    if extension.endswith(".csv"):
        try:
            return pd.read_csv(
                uploaded_file,
                sep=None,
                engine="python",
                encoding="utf-8-sig"
            )
        except Exception:
            uploaded_file.seek(0)

            return pd.read_csv(
                uploaded_file,
                sep=None,
                engine="python",
                encoding="latin1"
            )

    raise ValueError("Format file tidak didukung.")


# =====================================================
# 5. APPLICATION HEADER
# =====================================================

st.title("📊 APBD Analytics AI")

st.subheader(
    "Sistem Analisis Anggaran dan Realisasi APBD"
)

st.markdown("""
Sistem ini membantu menganalisis data Anggaran Pendapatan
dan Belanja Daerah (APBD) berdasarkan data yang diunggah
dari portal resmi DJPK Kementerian Keuangan.

Analisis meliputi anggaran, realisasi, persentase
penyerapan, sisa anggaran, dan rekomendasi berbasis AI.
""")

st.markdown(
    "[🌐 Buka Portal Data APBD DJPK]"
    "(https://djpk.kemenkeu.go.id/portal/data/apbd)"
)


# =====================================================
# 6. FILE UPLOADER
# =====================================================

st.header("📂 Upload Data APBD")

uploaded_file = st.file_uploader(
    "Unggah data APBD dari DJPK",
    type=["xlsx", "xls", "csv"]
)


if uploaded_file:

    try:

        df_original = read_uploaded_file(uploaded_file)

        if df_original.empty:
            st.error("File tidak memiliki data.")
            st.stop()

        df_original.columns = [
            str(column).strip()
            for column in df_original.columns
        ]

        st.success("Data berhasil dibaca!")

        st.subheader("📋 Preview Data")

        st.dataframe(
            df_original.head(10),
            use_container_width=True
        )

        # =================================================
        # 7. COLUMN MAPPING
        # =================================================

        st.header("⚙️ Penyesuaian Kolom")

        st.write(
            "Sesuaikan kolom file dengan kebutuhan analisis."
        )

        columns = list(df_original.columns)

        col1, col2, col3 = st.columns(3)

        category_default = find_column(
            columns,
            ["akun", "kategori", "uraian", "program", "nama"]
        )

        budget_default = find_column(
            columns,
            ["anggaran", "pagu", "budget"]
        )

        actual_default = find_column(
            columns,
            ["realisasi", "actual"]
        )

        category_col = col1.selectbox(
            "Kolom Kategori/Akun",
            columns,
            index=columns.index(category_default)
        )

        budget_col = col2.selectbox(
            "Kolom Anggaran/Pagu",
            columns,
            index=columns.index(budget_default)
        )

        actual_col = col3.selectbox(
            "Kolom Realisasi",
            columns,
            index=columns.index(actual_default)
        )

        # =================================================
        # 8. OPTIONAL FILTERS
        # =================================================

        st.header("🔎 Filter Data")

        filter_columns = [
            column for column in columns
            if any(
                word in column.lower()
                for word in [
                    "tahun",
                    "wilayah",
                    "daerah",
                    "pemda",
                    "provinsi",
                    "kabupaten",
                    "kota",
                    "periode"
                ]
            )
        ]

        df = df_original.copy()

        if filter_columns:

            filter_col = st.selectbox(
                "Pilih kolom filter",
                ["Tidak ada filter"] + filter_columns
            )

            if filter_col != "Tidak ada filter":

                filter_values = sorted(
                    df[filter_col]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

                selected_value = st.selectbox(
                    f"Pilih {filter_col}",
                    filter_values
                )

                df = df[
                    df[filter_col].astype(str)
                    == selected_value
                ]

        # =================================================
        # 9. DATA CLEANING
        # =================================================

        df = df.copy()

        df["Category"] = (
            df[category_col]
            .fillna("Tidak diketahui")
            .astype(str)
        )

        df["Budget"] = df[budget_col].apply(
            parse_number
        )

        df["Actual"] = df[actual_col].apply(
            parse_number
        )

        df = df[
            ["Category", "Budget", "Actual"]
        ]

        df = df.dropna(
            subset=["Category"]
        )

        # Menggabungkan akun dengan nama yang sama
        df = df.groupby(
            "Category",
            as_index=False
        ).agg({
            "Budget": "sum",
            "Actual": "sum"
        })

        # =================================================
        # 10. VARIANCE CALCULATION
        # =================================================

        df["Variance"] = (
            df["Actual"] - df["Budget"]
        )

        df["Variance %"] = (
            df["Variance"]
            / df["Budget"].replace(0, float("nan"))
        ) * 100

        df["Realization %"] = (
            df["Actual"]
            / df["Budget"].replace(0, float("nan"))
        ) * 100

        df["Remaining Budget"] = (
            df["Budget"] - df["Actual"]
        )

        # =================================================
        # 11. DATA PREVIEW
        # =================================================

        st.header("📊 Hasil Pengolahan Data")

        st.dataframe(
            df,
            use_container_width=True
        )

        # =================================================
        # 12. KEY PERFORMANCE INDICATORS
        # =================================================

        total_budget = df["Budget"].sum()

        total_actual = df["Actual"].sum()

        total_variance = (
            total_actual - total_budget
        )

        total_remaining = (
            total_budget - total_actual
        )

        realization_rate = (
            total_actual / total_budget * 100
            if total_budget != 0
            else 0
        )

        st.header("📌 Ringkasan APBD")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Anggaran",
            format_rupiah(total_budget)
        )

        col2.metric(
            "Total Realisasi",
            format_rupiah(total_actual)
        )

        col3.metric(
            "Persentase Realisasi",
            f"{realization_rate:.2f}%"
        )

        col4, col5 = st.columns(2)

        col4.metric(
            "Sisa Anggaran",
            format_rupiah(total_remaining)
        )

        col5.metric(
            "Selisih Realisasi",
            format_rupiah(total_variance)
        )

        # =================================================
        # 13. REALIZATION STATUS
        # =================================================

        st.header("📈 Analisis Penyerapan Anggaran")

        if realization_rate >= 90:
            st.success(
                "Realisasi anggaran berada pada tingkat tinggi."
            )

        elif realization_rate >= 70:
            st.info(
                "Realisasi anggaran berada pada tingkat sedang."
            )

        else:
            st.warning(
                "Realisasi anggaran masih relatif rendah."
            )

        # =================================================
        # 14. BUDGET VS ACTUAL CHART
        # =================================================

        st.subheader(
            "Perbandingan Anggaran dan Realisasi"
        )

        fig_budget = px.bar(
            df,
            x="Category",
            y=["Budget", "Actual"],
            barmode="group",
            title="Anggaran vs Realisasi per Akun"
        )

        st.plotly_chart(
            fig_budget,
            use_container_width=True
        )

        # =================================================
        # 15. REALIZATION PERCENTAGE CHART
        # =================================================

        st.subheader(
            "Persentase Realisasi per Akun"
        )

        fig_realization = px.bar(
            df,
            x="Category",
            y="Realization %",
            title="Tingkat Penyerapan Anggaran",
            text_auto=".2f"
        )

        fig_realization.add_hline(
            y=100,
            line_dash="dash",
            annotation_text="Target 100%"
        )

        st.plotly_chart(
            fig_realization,
            use_container_width=True
        )

        # =================================================
        # 16. VARIANCE ANALYSIS
        # =================================================

        st.subheader(
            "Analisis Selisih Anggaran"
        )

        fig_variance = px.bar(
            df,
            x="Category",
            y="Variance",
            title="Selisih Realisasi dan Anggaran",
            text_auto=".2s"
        )

        st.plotly_chart(
            fig_variance,
            use_container_width=True
        )

        # =================================================
        # 17. CATEGORY ANALYSIS
        # =================================================

        st.header("🔍 Akun dengan Realisasi Terendah")

        lowest = df.sort_values(
            "Realization %",
            ascending=True
        ).head(5)

        st.dataframe(
            lowest[
                [
                    "Category",
                    "Budget",
                    "Actual",
                    "Realization %",
                    "Remaining Budget"
                ]
            ],
            use_container_width=True
        )

        st.header("📊 Akun dengan Realisasi Tertinggi")

        highest = df.sort_values(
            "Realization %",
            ascending=False
        ).head(5)

        st.dataframe(
            highest[
                [
                    "Category",
                    "Budget",
                    "Actual",
                    "Realization %",
                    "Remaining Budget"
                ]
            ],
            use_container_width=True
        )

        # =================================================
        # 18. EXPORT RESULT
        # =================================================

        st.header("📥 Download Hasil Analisis")

        output = io.BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                index=False,
                sheet_name="Analisis APBD"
            )

        st.download_button(
            label="Download Hasil Analisis Excel",
            data=output.getvalue(),
            file_name="hasil_analisis_apbd.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            )
        )

        # =================================================
        # 19. AI-POWERED APBD ANALYSIS
        # =================================================

        st.header("🤖 AI-Powered APBD Analysis")

        if client is None:

            st.warning(
                "Gemini API Key belum tersedia. "
                "Tambahkan GEMINI_API_KEY pada file .env."
            )

        else:

            if st.button(
                "Generate AI APBD Analysis"
            ):

                with st.spinner(
                    "AI sedang menganalisis data APBD..."
                ):

                    financial_summary = df.to_string(
                        index=False
                    )

                    prompt = f"""
                    Anda adalah analis keuangan daerah
                    yang memahami APBD dan keuangan publik.

                    Analisis data APBD berikut:

                    {financial_summary}

                    Total Anggaran:
                    {total_budget:,.2f}

                    Total Realisasi:
                    {total_actual:,.2f}

                    Persentase Realisasi:
                    {realization_rate:.2f}%

                    Sisa Anggaran:
                    {total_remaining:,.2f}

                    Buat analisis dalam bahasa Indonesia
                    dengan struktur:

                    1. Ringkasan Eksekutif
                    2. Analisis Anggaran dan Realisasi
                    3. Akun dengan Realisasi Rendah
                    4. Akun dengan Realisasi Tinggi
                    5. Potensi Risiko Keuangan Daerah
                    6. Rekomendasi Pengelolaan APBD

                    Bedakan fakta data dengan kemungkinan
                    penyebab. Jangan mengarang penyebab
                    yang tidak tersedia dalam data.

                    Jelaskan bahwa realisasi rendah tidak
                    selalu berarti kinerja buruk karena
                    dapat dipengaruhi jadwal pelaksanaan,
                    karakteristik program, dan faktor lain.
                    """

                    try:

                        response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=prompt
                        )

                        st.markdown(response.text)

                    except Exception as e:

                        st.error(
                            f"Gemini API Error: {str(e)}"
                        )

        # =================================================
        # 20. AI CHAT
        # =================================================

        st.header("💬 Tanya AI tentang APBD")

        st.write(
            "Ajukan pertanyaan mengenai anggaran, "
            "realisasi, dan hasil analisis data."
        )

        user_query = st.text_input(
            "Contoh: Akun mana yang memiliki "
            "realisasi paling rendah?"
        )

        if st.button("Tanyakan kepada AI"):

            if not user_query.strip():

                st.warning(
                    "Masukkan pertanyaan terlebih dahulu."
                )

            elif client is None:

                st.error(
                    "Gemini API Key belum tersedia."
                )

            else:

                with st.spinner(
                    "AI sedang menyiapkan jawaban..."
                ):

                    prompt = f"""
                    Anda adalah asisten analis APBD.

                    Gunakan data berikut untuk menjawab
                    pertanyaan pengguna.

                    Data APBD:
                    {df.to_string(index=False)}

                    Total Anggaran:
                    {total_budget:,.2f}

                    Total Realisasi:
                    {total_actual:,.2f}

                    Persentase Realisasi:
                    {realization_rate:.2f}%

                    Pertanyaan:
                    {user_query}

                    Jawab dengan bahasa Indonesia yang
                    sederhana, jelas, dan berdasarkan data.

                    Jika informasi tidak tersedia,
                    sampaikan bahwa data belum cukup.

                    Jangan membuat angka atau fakta baru.
                    """

                    try:

                        chat_response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=prompt
                        )

                        st.markdown(
                            chat_response.text
                        )

                    except Exception as e:

                        st.error(
                            f"Gemini API Error: {str(e)}"
                        )

    except Exception as e:

        st.error(
            f"Terjadi kesalahan saat memproses file: {str(e)}"
        )
