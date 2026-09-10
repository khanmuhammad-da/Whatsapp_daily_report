import io
import re
from datetime import datetime, date
from typing import List, Dict, Optional

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="WhatsApp Daily Report Generator",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# CONSTANTS
# ============================================================

REPORT_COLUMNS = [
    "S.No",
    "Ticket No",
    "Start Date",
    "End Date",
    "Project Site",
    "Activities",
    "KE Representative",
    "Vendor Supervisor",
    "Manpower (Labour)",
]


# ============================================================
# PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>
        .main-title {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }

        .subtitle {
            color: #666666;
            margin-bottom: 1.5rem;
        }

        .metric-card {
            padding: 1rem;
            border-radius: 10px;
            border: 1px solid #dddddd;
            text-align: center;
        }

        .small-note {
            color: #666666;
            font-size: 0.85rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📊 WhatsApp Daily Report Generator</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="subtitle">
    Convert WhatsApp site activity messages into your daily manpower and work progress report.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATE PARSING
# ============================================================

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


def clean_text(value: str) -> str:
    """Clean whitespace and common WhatsApp formatting."""

    if value is None:
        return ""

    value = str(value)

    # Remove WhatsApp formatting markers
    value = value.replace("*", "")
    value = value.replace("_", "")
    value = value.replace("`", "")

    # Normalize whitespace
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_date_value(value: str, default_year: int) -> Optional[date]:
    """
    Parse common date formats found in WhatsApp messages.

    Examples:
        9.9.26
        09.09.2026
        9/9/26
        9th September
        9 September
        9 Sep
    """

    if not value:
        return None

    value = clean_text(value).lower()

    # Remove ordinal suffixes
    value = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", value)

    # Remove commas
    value = value.replace(",", " ")

    # --------------------------------------------------------
    # Numeric date
    # --------------------------------------------------------

    numeric_match = re.search(
        r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b",
        value,
    )

    if numeric_match:
        day = int(numeric_match.group(1))
        month = int(numeric_match.group(2))
        year = int(numeric_match.group(3))

        if year < 100:
            year += 2000

        try:
            return date(year, month, day)
        except ValueError:
            return None

    # --------------------------------------------------------
    # Day + month
    # --------------------------------------------------------

    month_pattern = (
        r"\b(\d{1,2})\s+"
        r"(january|jan|february|feb|march|mar|april|apr|may|"
        r"june|jun|july|jul|august|aug|september|sep|sept|"
        r"october|oct|november|nov|december|dec)"
        r"(?:\s+(\d{2,4}))?\b"
    )

    month_match = re.search(month_pattern, value)

    if month_match:
        day = int(month_match.group(1))
        month_name = month_match.group(2)
        year_value = month_match.group(3)

        month = MONTHS[month_name]

        if year_value:
            year = int(year_value)
            if year < 100:
                year += 2000
        else:
            year = default_year

        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


# ============================================================
# FIELD EXTRACTION
# ============================================================

FIELD_PATTERNS = {
    "ticket_no": [
        r"ticket\s*no\.?\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
        r"ticket\s*number\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
        r"ticket\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
    ],

    "start_date": [
        r"start\s*date\s*[:\-]?\s*(.+)",
    ],

    "end_date": [
        r"end\s*date\s*[:\-]?\s*(.+)",
    ],

    "project_site": [
        r"project\s*site\s*[:\-]?\s*(.+)",
        r"site\s*[:\-]?\s*(.+)",
    ],

    "activity": [
        r"activity\s*[:\-]?\s*(.+)",
        r"activities\s*[:\-]?\s*(.+)",
    ],

    "ke_supervisor": [
        r"ke\s*supervisor\s*[:\-]?\s*(.*)",
        r"ke\s*representative\s*[:\-]?\s*(.*)",
    ],

    "vendor_supervisor": [
        r"vendor\s*supervisor\s*[:\-]?\s*(.*)",
    ],

    "manpower": [
        r"manpower\s*[:\-]?\s*(.*)",
        r"man\s*power\s*[:\-]?\s*(.*)",
    ],
}


def extract_field(block: str, patterns: List[str]) -> str:
    """Extract a field from a WhatsApp ticket block."""

    for pattern in patterns:
        match = re.search(pattern, block, flags=re.IGNORECASE)

        if match:
            value = match.group(1).strip()

            # Stop at another bullet if it accidentally got included
            value = re.split(r"\n\s*\*", value)[0]

            return clean_text(value)

    return ""


def parse_manpower(value: str) -> Optional[int]:
    """
    Convert manpower text to integer.

    Examples:
        2nos
        2 nos
        2
        02
        2 persons
        2 labour
    """

    if not value:
        return None

    value = clean_text(value).lower()

    match = re.search(r"\b(\d+)\b", value)

    if match:
        return int(match.group(1))

    return None


# ============================================================
# SPLIT WHATSAPP MESSAGES INTO TICKETS
# ============================================================

def split_ticket_blocks(text: str) -> List[str]:
    """
    Split a WhatsApp export into separate ticket blocks.

    A new block is identified by:
        Ticket No. XXXXX
    """

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Normalize common WhatsApp bullet formats
    text = re.sub(r"(?m)^\s*[•●]\s*", "* ", text)

    # Locate each Ticket No.
    matches = list(
        re.finditer(
            r"(?im)^\s*\*?\s*ticket\s*(?:no\.?|number)?\s*[:\-]?\s*[A-Za-z0-9\-/]+",
            text,
        )
    )

    if not matches:
        return []

    blocks = []

    for i, match in enumerate(matches):

        start = match.start()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        block = text[start:end].strip()

        if block:
            blocks.append(block)

    return blocks


# ============================================================
# PARSE ONE TICKET
# ============================================================

def parse_ticket(block: str, default_year: int) -> Dict:

    ticket_no = extract_field(
        block,
        FIELD_PATTERNS["ticket_no"],
    )

    start_date_raw = extract_field(
        block,
        FIELD_PATTERNS["start_date"],
    )

    end_date_raw = extract_field(
        block,
        FIELD_PATTERNS["end_date"],
    )

    project_site = extract_field(
        block,
        FIELD_PATTERNS["project_site"],
    )

    activity = extract_field(
        block,
        FIELD_PATTERNS["activity"],
    )

    ke_supervisor = extract_field(
        block,
        FIELD_PATTERNS["ke_supervisor"],
    )

    vendor_supervisor = extract_field(
        block,
        FIELD_PATTERNS["vendor_supervisor"],
    )

    manpower_raw = extract_field(
        block,
        FIELD_PATTERNS["manpower"],
    )

    start_date = parse_date_value(
        start_date_raw,
        default_year,
    )

    end_date = parse_date_value(
        end_date_raw,
        default_year,
    )

    manpower = parse_manpower(manpower_raw)

    # --------------------------------------------------------
    # Treat "yes" as incomplete KE supervisor information
    # --------------------------------------------------------

    if ke_supervisor.lower() in [
        "yes",
        "y",
        "ok",
        "present",
    ]:
        ke_supervisor = ""

    return {
        "Ticket No": ticket_no,
        "Start Date": start_date.strftime("%d-%b-%Y")
        if start_date
        else "",

        "End Date": end_date.strftime("%d-%b-%Y")
        if end_date
        else "",

        "Project Site": project_site,
        "Activities": activity,
        "KE Representative": ke_supervisor,
        "Vendor Supervisor": vendor_supervisor,
        "Manpower (Labour)": manpower,
        "_raw_message": block,
    }


# ============================================================
# PARSE COMPLETE WHATSAPP FILE
# ============================================================

def parse_whatsapp_text(
    text: str,
    report_year: int,
) -> pd.DataFrame:

    blocks = split_ticket_blocks(text)

    records = []

    for block in blocks:

        record = parse_ticket(
            block,
            report_year,
        )

        records.append(record)

    if not records:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    df = pd.DataFrame(records)

    # --------------------------------------------------------
    # Remove exact duplicate tickets
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["Ticket No"],
        keep="last",
    )

    # --------------------------------------------------------
    # Add serial number
    # --------------------------------------------------------

    df.insert(
        0,
        "S.No",
        range(1, len(df) + 1),
    )

    return df


# ============================================================
# VALIDATION
# ============================================================

def find_missing_fields(row: pd.Series) -> List[str]:

    required_fields = {
        "Ticket No": "Ticket No",
        "Start Date": "Start Date",
        "End Date": "End Date",
        "Project Site": "Project Site",
        "Activities": "Activities",
        "Manpower (Labour)": "Manpower",
    }

    missing = []

    for column, label in required_fields.items():

        value = row.get(column)

        if pd.isna(value) or str(value).strip() == "":
            missing.append(label)

    return missing


def add_validation_columns(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    df["Missing Fields"] = df.apply(
        lambda row: ", ".join(find_missing_fields(row)),
        axis=1,
    )

    df["Status"] = df["Missing Fields"].apply(
        lambda value: "Incomplete"
        if value
        else "Complete"
    )

    return df


# ============================================================
# EXCEL GENERATION
# ============================================================

def generate_excel(
    df: pd.DataFrame,
    report_date: date,
) -> bytes:

    output = io.BytesIO()

    # Create report dataframe
    report_df = df[
        [
            "S.No",
            "Ticket No",
            "Start Date",
            "End Date",
            "Project Site",
            "Activities",
            "KE Representative",
            "Vendor Supervisor",
            "Manpower (Labour)",
        ]
    ].copy()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        report_df.to_excel(
            writer,
            index=False,
            sheet_name="Daily Report",
        )

        workbook = writer.book
        worksheet = writer.sheets["Daily Report"]

        # ----------------------------------------------------
        # Formatting
        # ----------------------------------------------------

        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter

        header_fill = PatternFill(
            fill_type="solid",
            fgColor="1F4E78",
        )

        header_font = Font(
            color="FFFFFF",
            bold=True,
        )

        for cell in worksheet[1]:

            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        # Column widths

        widths = {
            "A": 8,
            "B": 15,
            "C": 16,
            "D": 16,
            "E": 25,
            "F": 35,
            "G": 22,
            "H": 25,
            "I": 18,
        }

        for column, width in widths.items():
            worksheet.column_dimensions[column].width = width

        # Freeze header

        worksheet.freeze_panes = "A2"

        # Filter

        worksheet.auto_filter.ref = worksheet.dimensions

        # ----------------------------------------------------
        # Summary sheet
        # ----------------------------------------------------

        summary = pd.DataFrame(
            {
                "Metric": [
                    "Report Date",
                    "Total Tickets",
                    "Complete Tickets",
                    "Incomplete Tickets",
                    "Total Manpower",
                ],
                "Value": [
                    report_date.strftime("%d-%b-%Y"),
                    len(report_df),
                    int(
                        (
                            df["Status"]
                            == "Complete"
                        ).sum()
                    ),
                    int(
                        (
                            df["Status"]
                            == "Incomplete"
                        ).sum()
                    ),
                    int(
                        pd.to_numeric(
                            df[
                                "Manpower (Labour)"
                            ],
                            errors="coerce",
                        )
                        .fillna(0)
                        .sum()
                    ),
                ],
            }
        )

        summary.to_excel(
            writer,
            index=False,
            sheet_name="Summary",
        )

        summary_ws = writer.sheets["Summary"]

        summary_ws.column_dimensions["A"].width = 25
        summary_ws.column_dimensions["B"].width = 25

        for cell in summary_ws[1]:
            cell.fill = header_fill
            cell.font = header_font

    output.seek(0)

    return output.getvalue()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Report Settings")

    report_date = st.date_input(
        "Report Date",
        value=date.today(),
    )

    st.markdown("---")

    st.markdown(
        """
        **Workflow**

        1. Export WhatsApp chat
        2. Upload `.txt`
        3. Parse tickets
        4. Review records
        5. Generate Excel
        """
    )

    st.markdown("---")

    st.caption(
        "Version 1.0 — Local WhatsApp report parser"
    )


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("1. Upload WhatsApp Messages")

uploaded_file = st.file_uploader(
    "Upload WhatsApp chat export",
    type=["txt"],
    help=(
        "Export the WhatsApp group chat without media "
        "and upload the resulting TXT file."
    ),
)


# ============================================================
# MANUAL TEXT OPTION
# ============================================================

st.subheader("Or paste WhatsApp messages")

manual_text = st.text_area(
    "Paste messages here",
    height=250,
    placeholder=(
        "* Ticket No. 298662\n"
        "* Start Date 9.9.26\n"
        "* End Date 9.9.26\n"
        "* Project Site Queens road\n"
        "* Activity Paint work\n"
        "* KE Supervisor Zulfiqar\n"
        "* Vendor Supervisor Abdullah\n"
        "* Manpower 2nos\n"
    ),
)


# ============================================================
# GET INPUT TEXT
# ============================================================

input_text = ""

if uploaded_file is not None:

    try:

        input_text = uploaded_file.getvalue().decode(
            "utf-8-sig",
            errors="replace",
        )

        st.success(
            f"Uploaded: {uploaded_file.name}"
        )

    except Exception as exc:

        st.error(
            f"Could not read the uploaded file: {exc}"
        )

elif manual_text.strip():

    input_text = manual_text


# ============================================================
# PROCESS BUTTON
# ============================================================

if st.button(
    "🔍 Extract WhatsApp Reports",
    type="primary",
    use_container_width=True,
):

    if not input_text.strip():

        st.warning(
            "Please upload a WhatsApp TXT export or paste messages."
        )

    else:

        with st.spinner(
            "Extracting ticket information..."
        ):

            df = parse_whatsapp_text(
                input_text,
                report_date.year,
            )

            if df.empty:

                st.error(
                    "No ticket messages were detected. "
                    "Make sure the text contains 'Ticket No'."
                )

            else:

                df = add_validation_columns(df)

                st.session_state["report_df"] = df
                st.session_state["processed"] = True


# ============================================================
# DISPLAY RESULTS
# ============================================================

if st.session_state.get(
    "processed",
    False,
):

    df = st.session_state["report_df"]

    st.markdown("---")

    st.subheader("2. Extracted Reports")

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    total_tickets = len(df)

    complete = int(
        (df["Status"] == "Complete").sum()
    )

    incomplete = int(
        (df["Status"] == "Incomplete").sum()
    )

    manpower = int(
        pd.to_numeric(
            df["Manpower (Labour)"],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Tickets",
        total_tickets,
    )

    col2.metric(
        "Complete",
        complete,
    )

    col3.metric(
        "Incomplete",
        incomplete,
    )

    col4.metric(
        "Total Manpower",
        manpower,
    )

    st.markdown("---")

    # --------------------------------------------------------
    # Editable table
    # --------------------------------------------------------

    st.info(
        "Review and correct the extracted information below "
        "before generating the final report."
    )

    editable_columns = [
        "Ticket No",
        "Start Date",
        "End Date",
        "Project Site",
        "Activities",
        "KE Representative",
        "Vendor Supervisor",
        "Manpower (Labour)",
    ]

    edited_df = st.data_editor(
        df[
            editable_columns
        ],
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Ticket No": st.column_config.TextColumn(
                "Ticket No",
                required=True,
            ),

            "Start Date": st.column_config.TextColumn(
                "Start Date",
            ),

            "End Date": st.column_config.TextColumn(
                "End Date",
            ),

            "Project Site": st.column_config.TextColumn(
                "Project Site",
            ),

            "Activities": st.column_config.TextColumn(
                "Activities",
                width="large",
            ),

            "KE Representative": st.column_config.TextColumn(
                "KE Representative",
            ),

            "Vendor Supervisor": st.column_config.TextColumn(
                "Vendor Supervisor",
            ),

            "Manpower (Labour)": st.column_config.NumberColumn(
                "Manpower (Labour)",
                min_value=0,
                step=1,
            ),
        },
        key="editable_report",
    )

    # --------------------------------------------------------
    # Rebuild dataframe after editing
    # --------------------------------------------------------

    edited_df = edited_df.copy()

    edited_df.insert(
        0,
        "S.No",
        range(
            1,
            len(edited_df) + 1,
        ),
    )

    edited_df = add_validation_columns(
        edited_df
    )

    st.session_state["report_df"] = edited_df

    # --------------------------------------------------------
    # Show incomplete records
    # --------------------------------------------------------

    incomplete_df = edited_df[
        edited_df["Status"]
        == "Incomplete"
    ]

    if not incomplete_df.empty:

        st.warning(
            f"{len(incomplete_df)} ticket(s) "
            "still have missing information."
        )

        st.dataframe(
            incomplete_df[
                [
                    "Ticket No",
                    "Missing Fields",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.success(
            "All extracted tickets are complete."
        )

    # --------------------------------------------------------
    # Generate Excel
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader("3. Generate Daily Report")

    final_df = edited_df.copy()

    excel_data = generate_excel(
        final_df,
        report_date,
    )

    filename = (
        f"Daily_Report_"
        f"{report_date.strftime('%d-%m-%Y')}.xlsx"
    )

    st.download_button(
        label="📥 Download Daily Excel Report",
        data=excel_data,
        file_name=filename,
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True,
    )

    # --------------------------------------------------------
    # Preview final report
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader("4. Final Report Preview")

    st.dataframe(
        final_df[
            REPORT_COLUMNS
        ],
        use_container_width=True,
        hide_index=True,
    )