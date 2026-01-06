from app.db.supabase import get_supabase_client
from typing import List, Dict, Union
import logging
import json

logger = logging.getLogger(__name__)


def parse_json_field(value: Union[str, dict, None]) -> Union[dict, None]:
    """
    Parse a JSON string field into a dict.
    Handles JSONB fields that may come as strings from Supabase.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def parse_comma_separated(value: Union[str, List, None]) -> List[str]:
    """
    Parse comma-separated string or return list as-is.
    Handles the mismatch between VARCHAR storage (teachers) and array storage (schools).
    """
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str) and value:
        return [s.strip() for s in value.split(',') if s.strip()]
    return []


def parse_years_experience(value: Union[str, int, None]) -> int:
    """
    Parse years_experience from VARCHAR to int.
    Handles formats like "5", "5 years", "5+", etc.
    """
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # Extract first number from string
        import re
        match = re.search(r'\d+', value)
        if match:
            return int(match.group())
    return 0


class MatchingService:
    """
    Teacher-School Matching Algorithm

    Scoring weights (from PRD):
    - Location match: 35%
    - Subject specialty: 25%
    - Age group preference: 20%
    - Experience level: 15%
    - Chinese requirement: 5%
    """

    WEIGHT_LOCATION = 0.35
    WEIGHT_SUBJECT = 0.25
    WEIGHT_AGE_GROUP = 0.20
    WEIGHT_EXPERIENCE = 0.15
    WEIGHT_CHINESE = 0.05

    @staticmethod
    def calculate_location_score(teacher_locations: List[str], school_city: str, school_province: str) -> float:
        """
        Calculate location match score
        Returns 0-100
        """
        if not teacher_locations:
            return 50.0  # Neutral score if no preference

        # Exact city match
        for location in teacher_locations:
            if location.lower() == school_city.lower():
                return 100.0

        # Province match (partial)
        for location in teacher_locations:
            if location.lower() in school_province.lower() or school_province.lower() in location.lower():
                return 70.0

        # No match
        return 0.0

    @staticmethod
    def calculate_subject_score(teacher_subjects: List[str], school_subjects: List[str]) -> float:
        """
        Calculate subject specialty match score
        Returns 0-100
        """
        if not teacher_subjects or not school_subjects:
            return 50.0  # Neutral if no data

        # Convert to lowercase for comparison
        teacher_set = set([s.lower() for s in teacher_subjects])
        school_set = set([s.lower() for s in school_subjects])

        # Calculate overlap
        overlap = len(teacher_set & school_set)
        if overlap == 0:
            return 0.0

        # Score based on number of matching subjects
        score = (overlap / len(school_set)) * 100
        return min(score, 100.0)

    @staticmethod
    def calculate_age_group_score(teacher_age_groups: List[str], school_age_groups: List[str]) -> float:
        """
        Calculate age group preference match score
        Returns 0-100
        """
        if not teacher_age_groups or not school_age_groups:
            return 50.0  # Neutral if no data

        teacher_set = set([a.lower() for a in teacher_age_groups])
        school_set = set([a.lower() for a in school_age_groups])

        overlap = len(teacher_set & school_set)
        if overlap == 0:
            return 0.0

        # Score based on overlap
        score = (overlap / len(school_set)) * 100
        return min(score, 100.0)

    @staticmethod
    def calculate_experience_score(teacher_years: int, school_required: str) -> float:
        """
        Calculate experience level match score
        Returns 0-100

        School requirements typically: "0-2 years", "3-5 years", "5+ years"
        """
        if teacher_years is None:
            return 50.0  # Neutral if no data

        if not school_required:
            return 100.0  # No requirement = perfect match

        school_required = school_required.lower()

        # Parse school requirement
        if "5+" in school_required or "5 or more" in school_required:
            min_years = 5
            max_years = 999
        elif "-" in school_required:
            parts = school_required.split("-")
            try:
                min_years = int(parts[0].strip())
                max_years = int(parts[1].split()[0].strip())
            except:
                return 50.0  # Can't parse, neutral
        else:
            return 50.0  # Unknown format, neutral

        # Perfect match if within range
        if min_years <= teacher_years <= max_years:
            return 100.0

        # Partial match if close
        if abs(teacher_years - min_years) <= 1:
            return 80.0
        if abs(teacher_years - max_years) <= 1:
            return 80.0

        # Over-qualified (teacher has more experience than required)
        if teacher_years > max_years:
            # Slightly penalize over-qualification but still good
            excess = teacher_years - max_years
            return max(70.0 - (excess * 5), 30.0)

        # Under-qualified
        if teacher_years < min_years:
            shortage = min_years - teacher_years
            return max(50.0 - (shortage * 10), 0.0)

        return 50.0

    @staticmethod
    def calculate_chinese_score(teacher_has_chinese: bool, school_requires_chinese: bool) -> float:
        """
        Calculate Chinese language requirement match score
        Returns 0-100
        """
        if school_requires_chinese:
            return 100.0 if teacher_has_chinese else 0.0
        else:
            # No requirement, so teacher's Chinese is a bonus but not required
            return 100.0 if teacher_has_chinese else 90.0

    @staticmethod
    def calculate_match_score(teacher: Dict, school: Dict) -> tuple[float, List[str]]:
        """
        Calculate overall match score for teacher-school pair
        Returns (score, reasons)
        """
        # Extract teacher data (parse comma-separated strings from VARCHAR fields)
        teacher_locations = parse_comma_separated(teacher.get('preferred_location'))
        teacher_subjects = parse_comma_separated(teacher.get('subject_specialty'))
        teacher_age_groups = parse_comma_separated(teacher.get('preferred_age_group'))
        teacher_years = parse_years_experience(teacher.get('years_experience'))
        # has_chinese field doesn't exist yet - default to False
        teacher_has_chinese = teacher.get('has_chinese', False)

        # Extract school data
        school_city = school.get('city', '')
        school_province = school.get('province', '')
        school_subjects = school.get('subjects_needed', []) or []
        school_age_groups = school.get('age_groups', []) or []
        school_experience_req = school.get('experience_required', '')
        school_chinese_req = school.get('chinese_required', False)

        # Calculate component scores
        location_score = MatchingService.calculate_location_score(
            teacher_locations, school_city, school_province
        )
        subject_score = MatchingService.calculate_subject_score(
            teacher_subjects, school_subjects
        )
        age_group_score = MatchingService.calculate_age_group_score(
            teacher_age_groups, school_age_groups
        )
        experience_score = MatchingService.calculate_experience_score(
            teacher_years, school_experience_req
        )
        chinese_score = MatchingService.calculate_chinese_score(
            teacher_has_chinese, school_chinese_req
        )

        # Calculate weighted total score
        total_score = (
            location_score * MatchingService.WEIGHT_LOCATION +
            subject_score * MatchingService.WEIGHT_SUBJECT +
            age_group_score * MatchingService.WEIGHT_AGE_GROUP +
            experience_score * MatchingService.WEIGHT_EXPERIENCE +
            chinese_score * MatchingService.WEIGHT_CHINESE
        )

        # Generate match reasons
        reasons = []
        if location_score >= 70:
            reasons.append(f"Location match: {school_city}")
        if subject_score >= 70:
            matching_subjects = set([s.lower() for s in teacher_subjects]) & set([s.lower() for s in school_subjects])
            reasons.append(f"Subject match: {', '.join(matching_subjects)}")
        if age_group_score >= 70:
            matching_ages = set([a.lower() for a in teacher_age_groups]) & set([a.lower() for a in school_age_groups])
            reasons.append(f"Age group match: {', '.join(matching_ages)}")
        if experience_score >= 80:
            reasons.append(f"Experience level ({teacher_years} years) matches requirements")
        if chinese_score == 100 and school_chinese_req:
            reasons.append("Chinese language proficiency")

        return round(total_score, 2), reasons

    @staticmethod
    def run_matching_for_teacher(teacher_id: int, min_score: float = 50.0) -> List[Dict]:
        """
        Run matching algorithm for a single teacher
        Saves results to teacher_school_matches table
        Returns list of matches
        """
        supabase = get_supabase_client()

        # Get teacher data
        teacher_response = supabase.table("teachers").select("*").eq("id", teacher_id).single().execute()
        if not teacher_response.data:
            raise ValueError(f"Teacher {teacher_id} not found")

        teacher = teacher_response.data

        # Get all active schools
        schools_response = supabase.table("schools").select("*").eq("is_active", True).execute()
        schools = schools_response.data or []

        logger.info(f"Running matching for teacher {teacher_id} against {len(schools)} schools")

        matches = []
        for school in schools:
            score, reasons = MatchingService.calculate_match_score(teacher, school)

            if score >= min_score:
                match_data = {
                    "teacher_id": teacher_id,
                    "school_id": school["id"],
                    "match_score": score,
                    "match_reasons": reasons,
                }
                matches.append({
                    **match_data,
                    "school_city": school.get("city"),
                    "school_province": school.get("province"),
                    "salary_range": school.get("salary_range"),
                    "school_type": school.get("school_type"),
                })

        # Sort by score descending
        matches.sort(key=lambda x: x["match_score"], reverse=True)

        # Save to database (delete old matches first)
        supabase.table("teacher_school_matches").delete().eq("teacher_id", teacher_id).execute()

        if matches:
            # Save top matches
            for match in matches:
                # Only save match_data fields to database
                db_match = {
                    "teacher_id": match["teacher_id"],
                    "school_id": match["school_id"],
                    "match_score": match["match_score"],
                    "match_reasons": match["match_reasons"],
                }
                supabase.table("teacher_school_matches").insert(db_match).execute()

        logger.info(f"Found {len(matches)} matches for teacher {teacher_id}")
        return matches

    @staticmethod
    def get_teacher_matches(teacher_id: int, limit: int = 20) -> List[Dict]:
        """
        Get saved matches for a teacher (for display)
        Returns anonymous match data (no school names)
        """
        supabase = get_supabase_client()

        # Get matches with school data (using inner join)
        response = supabase.table("teacher_school_matches").select(
            "*, schools(city, province, school_type, age_groups, salary_range)"
        ).eq("teacher_id", teacher_id).order("match_score", desc=True).limit(limit).execute()

        matches = response.data or []

        # Transform to anonymous format
        anonymous_matches = []
        for match in matches:
            school_data = match.get("schools", {})
            anonymous_matches.append({
                "id": match["id"],
                "city": school_data.get("city"),
                "province": school_data.get("province"),
                "school_type": school_data.get("school_type"),
                "age_groups": school_data.get("age_groups", []),
                "salary_range": school_data.get("salary_range"),
                "match_score": match["match_score"],
                "match_reasons": match["match_reasons"],
                "is_submitted": match.get("is_submitted", False),
                "role_name": match.get("role_name"),
            })

        return anonymous_matches

    @staticmethod
    def run_matching_for_school(school_id: int, min_score: float = 50.0) -> int:
        """
        Run matching algorithm for a single school against all teachers.
        Upserts results to teacher_school_matches table.
        Returns count of matches created/updated.
        """
        supabase = get_supabase_client()

        # Get school data
        school_response = supabase.table("schools").select("*").eq("id", school_id).eq("is_active", True).single().execute()
        if not school_response.data:
            logger.warning(f"School {school_id} not found or not active")
            return 0

        school = school_response.data

        # Get all teachers
        teachers_response = supabase.table("teachers").select("*").execute()
        teachers = teachers_response.data or []

        logger.info(f"Running matching for school {school_id} against {len(teachers)} teachers")

        match_count = 0
        for teacher in teachers:
            score, reasons = MatchingService.calculate_match_score(teacher, school)

            if score >= min_score:
                match_data = {
                    "teacher_id": teacher["id"],
                    "school_id": school_id,
                    "match_score": score,
                    "match_reasons": reasons,
                }
                # Use upsert to handle existing matches
                supabase.table("teacher_school_matches").upsert(
                    match_data,
                    on_conflict="teacher_id,school_id"
                ).execute()
                match_count += 1
            else:
                # Remove match if score dropped below threshold
                supabase.table("teacher_school_matches").delete().eq(
                    "teacher_id", teacher["id"]
                ).eq("school_id", school_id).execute()

        logger.info(f"Found {match_count} matches for school {school_id}")
        return match_count

    @staticmethod
    def get_school_matches(school_id: int, limit: int = 50) -> List[Dict]:
        """
        Get matched teachers for a school (for admin display).
        Returns full teacher details with match scores.
        """
        supabase = get_supabase_client()

        response = supabase.table("teacher_school_matches").select(
            "*, teachers(id, first_name, last_name, email, subject_specialty, "
            "preferred_location, preferred_age_group, years_experience, status, has_paid)"
        ).eq("school_id", school_id).order("match_score", desc=True).limit(limit).execute()

        matches = []
        for match in response.data or []:
            teacher = match.get("teachers", {}) or {}
            matches.append({
                "match_id": match["id"],
                "match_score": match["match_score"],
                "match_reasons": match["match_reasons"],
                "is_submitted": match.get("is_submitted", False),
                "role_name": match.get("role_name"),
                "teacher_id": teacher.get("id"),
                "teacher_name": f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip(),
                "teacher_email": teacher.get("email"),
                "subject_specialty": teacher.get("subject_specialty"),
                "preferred_location": teacher.get("preferred_location"),
                "preferred_age_group": teacher.get("preferred_age_group"),
                "years_experience": teacher.get("years_experience"),
                "status": teacher.get("status"),
                "has_paid": teacher.get("has_paid", False),
            })

        return matches

    # ========================================
    # JOB MATCHING METHODS (for external jobs)
    # ========================================

    @staticmethod
    def calculate_job_match_score(teacher: Dict, job: Dict) -> tuple[float, List[str]]:
        """
        Calculate overall match score for teacher-job pair.
        Similar to school matching but uses job table fields.
        Returns (score, reasons)
        """
        # Extract teacher data (parse comma-separated strings from VARCHAR fields)
        teacher_locations = parse_comma_separated(teacher.get('preferred_location'))
        teacher_subjects = parse_comma_separated(teacher.get('subject_specialty'))
        teacher_age_groups = parse_comma_separated(teacher.get('preferred_age_group'))
        teacher_years = parse_years_experience(teacher.get('years_experience'))
        teacher_has_chinese = teacher.get('has_chinese', False)

        # Extract job data (jobs use 'subjects' not 'subjects_needed')
        job_city = job.get('city', '') or ''
        job_province = job.get('province', '') or ''
        job_subjects = job.get('subjects', []) or []
        job_age_groups = job.get('age_groups', []) or []
        job_experience_req = job.get('experience', '') or ''
        job_chinese_req = job.get('chinese_required', False)

        # Calculate component scores using existing methods
        location_score = MatchingService.calculate_location_score(
            teacher_locations, job_city, job_province
        )
        subject_score = MatchingService.calculate_subject_score(
            teacher_subjects, job_subjects
        )
        age_group_score = MatchingService.calculate_age_group_score(
            teacher_age_groups, job_age_groups
        )
        experience_score = MatchingService.calculate_experience_score(
            teacher_years, job_experience_req
        )
        chinese_score = MatchingService.calculate_chinese_score(
            teacher_has_chinese, job_chinese_req
        )

        # Calculate weighted total score
        total_score = (
            location_score * MatchingService.WEIGHT_LOCATION +
            subject_score * MatchingService.WEIGHT_SUBJECT +
            age_group_score * MatchingService.WEIGHT_AGE_GROUP +
            experience_score * MatchingService.WEIGHT_EXPERIENCE +
            chinese_score * MatchingService.WEIGHT_CHINESE
        )

        # Generate match reasons
        reasons = []
        if location_score >= 70:
            city_display = job_city or job_province or 'China'
            reasons.append(f"Location match: {city_display}")
        if subject_score >= 70 and teacher_subjects and job_subjects:
            matching_subjects = set([s.lower() for s in teacher_subjects]) & set([s.lower() for s in job_subjects])
            reasons.append(f"Subject match: {', '.join(matching_subjects)}")
        if age_group_score >= 70 and teacher_age_groups and job_age_groups:
            matching_ages = set([a.lower() for a in teacher_age_groups]) & set([a.lower() for a in job_age_groups])
            reasons.append(f"Age group match: {', '.join(matching_ages)}")
        if experience_score >= 80:
            reasons.append(f"Experience level ({teacher_years} years) matches requirements")
        if chinese_score == 100 and job_chinese_req:
            reasons.append("Chinese language proficiency")

        return round(total_score, 2), reasons

    @staticmethod
    def run_matching_for_job(job_id: int, min_score: float = 50.0) -> int:
        """
        Run matching algorithm for a job against all teachers.
        Saves results to teacher_school_matches table with job_id set.
        Returns count of matches created.
        """
        supabase = get_supabase_client()

        # Get job data
        job_response = supabase.table("jobs").select("*").eq("id", job_id).eq("is_active", True).single().execute()
        if not job_response.data:
            logger.warning(f"Job {job_id} not found or not active")
            return 0

        job = job_response.data

        # Get all teachers
        teachers_response = supabase.table("teachers").select("*").execute()
        teachers = teachers_response.data or []

        logger.info(f"Running matching for job {job_id} against {len(teachers)} teachers")

        match_count = 0
        for teacher in teachers:
            score, reasons = MatchingService.calculate_job_match_score(teacher, job)

            if score >= min_score:
                match_data = {
                    "teacher_id": teacher["id"],
                    "job_id": job_id,
                    "school_id": None,  # Jobs don't have school_id
                    "match_score": score,
                    "match_reasons": reasons,
                }

                # Check if match already exists for this teacher-job pair
                existing = supabase.table("teacher_school_matches").select("id").eq(
                    "teacher_id", teacher["id"]
                ).eq("job_id", job_id).execute()

                if existing.data:
                    # Update existing
                    supabase.table("teacher_school_matches").update({
                        "match_score": score,
                        "match_reasons": reasons,
                    }).eq("id", existing.data[0]["id"]).execute()
                else:
                    # Insert new
                    supabase.table("teacher_school_matches").insert(match_data).execute()

                match_count += 1
            else:
                # Remove match if score dropped below threshold
                supabase.table("teacher_school_matches").delete().eq(
                    "teacher_id", teacher["id"]
                ).eq("job_id", job_id).execute()

        logger.info(f"Found {match_count} matches for job {job_id}")
        return match_count

    @staticmethod
    def get_teacher_all_matches(teacher_id: int, limit: int = 50) -> List[Dict]:
        """
        Get all matches for a teacher (both school and job matches).
        Returns combined list sorted by match score.
        Includes expiry_date from applications for submitted matches.
        """
        supabase = get_supabase_client()

        # Get all matches (both school and job) with related application data
        response = supabase.table("teacher_school_matches").select(
            "*, schools(city, province, school_type, age_groups, salary_range), "
            "jobs(city, province, location_chinese, school_type, age_groups, salary, title, company, "
            "application_deadline, start_date, visa_sponsorship, accommodation_provided, "
            "external_url, source, description, chinese_required, qualification, contract_type, "
            "job_functions, requirements, benefits, subjects, is_new, contract_term, job_type, "
            "apply_by, recruiter_email, recruiter_phone, about_school, school_address), "
            "teacher_school_applications(expiry_date, role_name)"
        ).eq("teacher_id", teacher_id).order("match_score", desc=True).limit(limit).execute()

        matches = response.data or []

        # Transform to unified format
        unified_matches = []
        for match in matches:
            school_data = match.get("schools")
            job_data = match.get("jobs")
            # Get application data (may be a list, take first if exists)
            app_data = match.get("teacher_school_applications")
            if isinstance(app_data, list) and app_data:
                app_data = app_data[0]
            elif not isinstance(app_data, dict):
                app_data = {}

            # Get expiry_date and role_name from application if available
            expiry_date = app_data.get("expiry_date") if app_data else None
            # Prefer role_name from application, fall back to match
            role_name = app_data.get("role_name") if app_data else match.get("role_name")
            if not role_name:
                role_name = match.get("role_name")

            if school_data:
                # School match
                unified_matches.append({
                    "id": match["id"],
                    "type": "school",
                    "city": school_data.get("city"),
                    "province": school_data.get("province"),
                    "school_type": school_data.get("school_type"),
                    "age_groups": school_data.get("age_groups", []),
                    "salary_range": school_data.get("salary_range"),
                    "match_score": match["match_score"],
                    "match_reasons": match["match_reasons"],
                    "is_submitted": match.get("is_submitted", False),
                    "role_name": role_name,
                    "expiry_date": expiry_date,
                    # School-specific (null for jobs)
                    "school_id": match.get("school_id"),
                    "job_id": None,
                    # Job-specific fields (null for schools)
                    "title": None,
                    "company": None,
                    "application_deadline": None,
                    "start_date": None,
                    "visa_sponsorship": None,
                    "accommodation_provided": None,
                    "external_url": None,
                    "source": "manual",
                    "description": None,
                })
            elif job_data:
                # Job match - use job title as role_name if not set
                job_role_name = role_name or job_data.get("title")
                # Use application_deadline as expiry_date if not set
                job_expiry_date = expiry_date or job_data.get("application_deadline")

                unified_matches.append({
                    "id": match["id"],
                    "type": "job",
                    "city": job_data.get("city"),
                    "province": job_data.get("province"),
                    "location_chinese": job_data.get("location_chinese"),
                    "school_type": job_data.get("school_type"),
                    "age_groups": job_data.get("age_groups", []),
                    "subjects": job_data.get("subjects", []),
                    "salary_range": job_data.get("salary"),  # Jobs use 'salary' not 'salary_range'
                    "match_score": match["match_score"],
                    "match_reasons": match["match_reasons"],
                    "is_submitted": match.get("is_submitted", False),
                    "role_name": job_role_name,
                    "expiry_date": job_expiry_date,
                    # School-specific (null for jobs)
                    "school_id": None,
                    "job_id": match.get("job_id"),
                    # Job-specific fields
                    "title": job_data.get("title"),
                    "company": job_data.get("company"),
                    "application_deadline": job_data.get("application_deadline"),
                    "start_date": job_data.get("start_date"),
                    "visa_sponsorship": job_data.get("visa_sponsorship"),
                    "accommodation_provided": job_data.get("accommodation_provided"),
                    "external_url": job_data.get("external_url"),
                    "source": job_data.get("source", "tes"),
                    "description": job_data.get("description"),
                    # New fields from job detail pages
                    "chinese_required": job_data.get("chinese_required"),
                    "qualification": job_data.get("qualification"),
                    "contract_type": job_data.get("contract_type"),
                    "job_functions": job_data.get("job_functions"),
                    "requirements": job_data.get("requirements"),
                    "benefits": job_data.get("benefits"),
                    "is_new": job_data.get("is_new"),
                    "contract_term": job_data.get("contract_term"),
                    "job_type": job_data.get("job_type"),
                    "apply_by": job_data.get("apply_by"),
                    "recruiter_email": job_data.get("recruiter_email"),
                    "recruiter_phone": job_data.get("recruiter_phone"),
                    "about_school": job_data.get("about_school"),
                    "school_address": parse_json_field(job_data.get("school_address")),
                })

        return unified_matches

    @staticmethod
    def run_matching_for_teacher_jobs(teacher_id: int, min_score: float = 50.0) -> int:
        """
        Run matching algorithm for a teacher against all active external jobs.
        Saves results to teacher_school_matches table with job_id set.
        Returns count of matches created.
        """
        supabase = get_supabase_client()

        # Get teacher data
        teacher_response = supabase.table("teachers").select("*").eq("id", teacher_id).single().execute()
        if not teacher_response.data:
            raise ValueError(f"Teacher {teacher_id} not found")

        teacher = teacher_response.data

        # Get all active external jobs (source != 'manual')
        jobs_response = supabase.table("jobs").select("*").eq(
            "is_active", True
        ).neq("source", "manual").execute()
        jobs = jobs_response.data or []

        logger.info(f"Running job matching for teacher {teacher_id} against {len(jobs)} external jobs")

        match_count = 0
        for job in jobs:
            score, reasons = MatchingService.calculate_job_match_score(teacher, job)

            if score >= min_score:
                match_data = {
                    "teacher_id": teacher_id,
                    "job_id": job["id"],
                    "school_id": None,
                    "match_score": score,
                    "match_reasons": reasons,
                }

                # Check if match already exists
                existing = supabase.table("teacher_school_matches").select("id").eq(
                    "teacher_id", teacher_id
                ).eq("job_id", job["id"]).execute()

                if existing.data:
                    # Update existing
                    supabase.table("teacher_school_matches").update({
                        "match_score": score,
                        "match_reasons": reasons,
                    }).eq("id", existing.data[0]["id"]).execute()
                else:
                    # Insert new
                    supabase.table("teacher_school_matches").insert(match_data).execute()

                match_count += 1

        logger.info(f"Found {match_count} job matches for teacher {teacher_id}")
        return match_count
