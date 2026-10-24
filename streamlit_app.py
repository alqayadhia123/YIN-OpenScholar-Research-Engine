"""Bilingual local Streamlit UI for the YIN FastAPI service."""
import os
import requests
import pandas as pd
import streamlit as st

# Streamlit Community Cloud stores settings in st.secrets; local/container runs may use env vars.
try:
    _secret_api = st.secrets.get("YIN_API_URL", "")
except Exception:
    _secret_api = ""
DEFAULT_API = os.getenv("YIN_API_URL", _secret_api or "http://127.0.0.1:8000")
st.set_page_config(page_title="YIN Research Engine", page_icon="📚", layout="wide")

with st.sidebar:
    language = st.radio("Language / اللغة", ["العربية", "English"], horizontal=True)
    api_url = st.text_input("FastAPI URL", DEFAULT_API).rstrip("/")
    st.caption("Local interface · واجهة محلية")
    st.markdown("---")
    st.markdown("**YIN v0.4.0**")
    st.caption("Research discovery is not a completed systematic review.")

ar = language == "العربية"
def t(en, ar_text): return ar_text if ar else en
st.title(t("YIN — Research Literature Dashboard", "YIN — لوحة محرك البحث الأدبيات العلمية"))
st.caption(t("OpenAlex discovery · Crossref DOI metadata · SQLite history · optional synthesis and semantic audit", "استرجاع OpenAlex · بيانات DOI من Crossref · سجل SQLite · توليف وتدقيق دلالي اختياري"))

try:
    health = requests.get(f"{api_url}/health", timeout=4).json()
    st.success(t(f"API connected · version {health.get('version')}", f"الاتصال بالخادم ناجح · الإصدار {health.get('version')}"))
except Exception as exc:
    st.error(t(f"Cannot reach FastAPI: {exc}. Start it with: uvicorn app:app --reload", f"تعذر الاتصال بـ FastAPI: {exc}. شغّل الخادم بالأمر: uvicorn app:app --reload"))

search_tab, history_tab, export_tab = st.tabs([t("Search & Review", "البحث والمراجعة"), t("Run History", "سجل العمليات"), t("Reference Export", "تصدير المراجع")])
with search_tab:
    with st.form("search_form"):
        query = st.text_area(t("Research question / query", "سؤال البحث / الاستعلام"), placeholder=t("e.g. administrative process reengineering and university performance", "مثال: إعادة هندسة العمليات الإدارية والأداء الجامعي"), height=90)
        c1,c2,c3,c4 = st.columns(4)
        limit = c1.slider(t("Maximum records", "الحد الأقصى للدراسات"), 1, 25, 10)
        year_from = c2.number_input(t("From year (0 = none)", "من سنة (0 = بلا تحديد)"), min_value=0, max_value=2100, value=2020)
        year_to = c3.number_input(t("To year (0 = none)", "إلى سنة (0 = بلا تحديد)"), min_value=0, max_value=2100, value=0)
        oa = c4.checkbox(t("Open access only", "الوصول المفتوح فقط"), value=False)
        synthesis = st.checkbox(t("Request synthesis through configured OpenScholar bridge", "طلب توليف عبر جسر OpenScholar المهيأ"), value=False)
        audit = st.checkbox(t("Run semantic claim audit (requires LLM environment settings)", "تشغيل تدقيق الادعاءات (يتطلب إعداد خدمة LLM)"), value=False)
        include_exports = st.checkbox(t("Include reference exports in response", "إرفاق صيغ المراجع في الاستجابة"), value=True)
        submitted = st.form_submit_button(t("Search and save run", "ابحث واحفظ العملية"), type="primary")
    if submitted:
        if len(query.strip()) < 3:
            st.warning(t("Enter a query of at least 3 characters.", "أدخل استعلامًا لا يقل عن ثلاثة أحرف."))
        else:
            payload = {"query":query.strip(), "limit":limit, "year_from":year_from or None, "year_to":year_to or None,
                       "open_access_only":oa, "include_synthesis":synthesis, "run_semantic_audit":audit, "export_references":include_exports}
            with st.spinner(t("Searching providers and saving the run…", "جارٍ البحث وحفظ العملية…")):
                try:
                    response=requests.post(f"{api_url}/review", json=payload, timeout=240)
                    response.raise_for_status(); result=response.json(); st.session_state["yin_last_result"]=result
                except Exception as exc:
                    st.error(t(f"Request failed: {exc}", f"فشل الطلب: {exc}")); result=None
            if result:
                st.success(t(f"Saved run #{result.get('run_id')} · {result.get('count',0)} records", f"حُفظت العملية رقم {result.get('run_id')} · عدد السجلات {result.get('count',0)}"))
    result=st.session_state.get("yin_last_result")
    if result:
        st.subheader(t("Retrieved studies", "الدراسات المسترجعة"))
        papers=result.get("papers",[])
        if papers:
            df=pd.DataFrame([{t("Title","العنوان"):p.get("title"),t("Year","السنة"):p.get("year"),t("Authors","المؤلفون"):"; ".join(p.get("authors") or []),"DOI":p.get("doi"),t("Journal","المجلة"):p.get("journal"),t("Open access","وصول مفتوح"):p.get("open_access"),t("Landing page","رابط الدراسة"):p.get("landing_page")} for p in papers])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(t("Download papers JSON", "تنزيل الدراسات JSON"), data=__import__('json').dumps(papers,ensure_ascii=False,indent=2), file_name=f"yin_run_{result.get('run_id')}_papers.json", mime="application/json")
        with st.expander(t("Evidence report", "تقرير الأدلة"), expanded=True): st.markdown(result.get("report_markdown", ""))
        sem=result.get("semantic_audit")
        if sem:
            st.subheader(t("Semantic audit", "التدقيق الدلالي")); st.info(f"Status: {sem.get('status','unknown')} — {sem.get('reason','')}")
            if sem.get("audit_summary"):
                st.json(sem["audit_summary"])
                details=sem.get("detailed_audit",[])
                if details: st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True)
                unref=sem.get("unreferenced_claims",[])
                if unref:
                    st.warning(t("Unreferenced factual claims", "ادعاءات واقعية بلا استشهاد"))
                    for claim in unref: st.write("- "+claim)
        if result.get("synthesis"):
            with st.expander(t("Synthesis result", "نتيجة التوليف"), expanded=True): st.write(result["synthesis"])

with history_tab:
    if st.button(t("Refresh run history", "تحديث سجل العمليات")):
        st.session_state["yin_runs_refresh"]=True
    try:
        data=requests.get(f"{api_url}/runs", params={"limit":100}, timeout=10); data.raise_for_status(); runs=data.json().get("runs",[])
        if runs:
            st.dataframe(pd.DataFrame(runs), use_container_width=True, hide_index=True)
            selected=st.number_input(t("Open run ID", "فتح رقم العملية"), min_value=1, step=1)
            if st.button(t("Load selected run", "تحميل العملية المحددة")):
                detail=requests.get(f"{api_url}/runs/{int(selected)}",timeout=15)
                if detail.ok: st.json(detail.json())
                else: st.warning(t("Run not found.", "العملية غير موجودة."))
        else: st.info(t("No saved runs yet.", "لا توجد عمليات محفوظة بعد."))
    except Exception as exc: st.warning(t(f"History unavailable: {exc}", f"السجل غير متاح: {exc}"))

with export_tab:
    st.write(t("Export references from the most recent search result, or paste a JSON array of paper records.", "صدّر مراجع آخر عملية بحث أو الصق مصفوفة JSON لسجلات الدراسات."))
    last=st.session_state.get("yin_last_result",{}).get("papers",[])
    raw=st.text_area("Papers JSON", value=__import__('json').dumps(last,ensure_ascii=False,indent=2) if last else "[]", height=220)
    fmt=st.selectbox(t("Format", "الصيغة"), ["apa7","bibtex","ris"])
    if st.button(t("Generate export", "إنشاء التصدير")):
        try:
            import json
            papers=json.loads(raw)
            response=requests.post(f"{api_url}/export/{fmt}",json={"papers":papers},timeout=20); response.raise_for_status()
            filenames={"apa7":"references_apa7.txt","bibtex":"references.bib","ris":"references.ris"}
            mime={"apa7":"text/plain","bibtex":"application/x-bibtex","ris":"application/x-research-info-systems"}
            st.download_button(t("Download file", "تنزيل الملف"), data=response.text, file_name=filenames[fmt], mime=mime[fmt])
            st.code(response.text, language="text")
        except Exception as exc: st.error(t(f"Export failed: {exc}", f"فشل التصدير: {exc}"))
