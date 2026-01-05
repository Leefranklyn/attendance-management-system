from datetime import datetime

def parse_matric(matric: str):

    matric = matric.strip().upper()
    parts = matric.split('/')
    
    if len(parts) < 4:
        return None, None, None
    
    dept_code = parts[1]
    year_str = parts[2]
    
    dept_mapping = {
        'CSC': 'Computer Science',
        'PHY': 'Physics',
        'CHM': 'Chemistry',
        'MAT': 'Mathematics',
        'BIO': 'Biology',
        'ENG': 'English',
        'ACC': 'Accounting',
        'ECO': 'Economics',
        # Add more as needed
    }
    
    dept_name = dept_mapping.get(dept_code)
    try:
        enroll_year = 2000 + int(year_str)
    except ValueError:
        enroll_year = None
    
    sequence = parts[3] if len(parts) > 3 else None
    
    return dept_name, enroll_year, sequence


def calculate_current_level(enrollment_year: int) -> int:
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    session_start_year = current_year if current_month >= 10 else current_year - 1
    level = session_start_year - enrollment_year + 1
    return max(level, 1)