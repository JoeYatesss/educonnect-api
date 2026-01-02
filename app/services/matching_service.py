from app.db.supabase import get_supabase_client
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


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
        # Extract teacher data
        teacher_locations = teacher.get('preferred_location', []) or []
        teacher_subjects = teacher.get('subject_specialty', []) or []
        teacher_age_groups = teacher.get('preferred_age_group', []) or []
        teacher_years = teacher.get('years_experience', 0) or 0
        teacher_has_chinese = teacher.get('has_chinese', False)  # TODO: Add to schema

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
            })

        return anonymous_matches
