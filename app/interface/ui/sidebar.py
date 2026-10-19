# ui/components/sidebar.py

import streamlit as st

from config import DB_PATH
from utils.logging import get_logger
from typing import Dict, List, Optional, Callable




from pathlib import Path

logger = get_logger(__name__)

# Base directory: parent of the current file's directory
# If this file is in app/interface/, this points to app/interface/
BASE_DIR = Path(__file__).resolve().parent.parent

# Pages directory
PAGES_DIR = BASE_DIR / "pages"


def _page_path(filename: str) -> str:
    """
    Build full path to a page file.

    Args:
        filename: Page filename, e.g., "1_students.py"

    Returns:
        Absolute path as string.
    """
    return str(PAGES_DIR / filename)

def render_grouped_sidebar(
    extra_sidebar_content: Optional[Callable[[], None]] = None,
) -> None:
    """
    Render navigation sidebar with optional extra content.

    Args:
        extra_sidebar_content: Optional function that renders
            additional sidebar elements for the current page.
    """

    all_pages = {
         'main': st.Page(
            _page_path("0_home.py"),  # Must be a separate file, NOT your main router script!
            title="Dashboard",
            icon="🏠",
            default=True  # Optional: makes this the landing page
        ),
        'students': st.Page(
            _page_path("1_students.py"),
            title="Students",
            icon="👨‍🎓",
            
        ),
        'classes': st.Page(
            _page_path("2_classes.py"),
            title="Class Schedule",
            icon="🏋️",
        ),
        'payments': st.Page(
            _page_path("3_payments.py"),
            title="Payments",
            icon="💰",
        ),
        'attendance': st.Page(
            _page_path("4_attendance.py"),
            title="Attendance",
            icon="✅",
        ),
        'finance': st.Page(
            _page_path("6_financial_data.py"),
            title="Finance & Expenses",
            icon="📊",
        ),
        'trainers': st.Page(
            _page_path('7_trainers.py'),
            title='Trainers',
        ),
        'plans': st.Page(
            _page_path('5_plans.py')
        ),
        'expenses': st.Page(
            _page_path('9_expenses.py')
        ),
        're_expenses': st.Page(
            _page_path('10_re_expenses.py')
        ),
        'membership': st.Page(
            _page_path('11_memberships.py')
        ),
        'payees' : st.Page(
            _page_path('12_payees.py')
        )
    }

    
    nav_groups: Dict[str, List[st.Page]] = {}

    nav_groups['Main'] = [all_pages['main'], all_pages['students'], all_pages['trainers'], all_pages['membership']]

    
    nav_groups['Operation'] = [
        all_pages[key]
        for key in ('classes', 'attendance')
    ]
    
    nav_groups['Finance'] = [
        all_pages[key]
        for key in ('payments', 'finance', 'plans', 'expenses', 're_expenses', 'payees')
    ]
    

    
    nav = st.navigation(nav_groups)

    nav.run()
