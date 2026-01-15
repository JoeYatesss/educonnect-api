-- Migration: Normalize teacher preference values
-- This fixes inconsistencies between how values were stored during signup vs profile editing
-- and ensures filter matching works correctly

-- Normalize age groups: Convert lowercase_snake_case to Title Case
UPDATE teachers
SET preferred_age_group = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(preferred_age_group, 'kindergarten', 'Kindergarten'),
                'primary', 'Primary'
            ),
            'middle_school', 'Middle School'
        ),
        'high_school', 'High School'
    ),
    'university', 'University'
)
WHERE preferred_age_group IS NOT NULL
  AND (
    preferred_age_group ILIKE '%kindergarten%'
    OR preferred_age_group ILIKE '%primary%'
    OR preferred_age_group ILIKE '%middle_school%'
    OR preferred_age_group ILIKE '%high_school%'
    OR preferred_age_group ILIKE '%university%'
  );

-- Normalize subjects: PE -> Physical Education
UPDATE teachers
SET subject_specialty = REPLACE(subject_specialty, 'PE', 'Physical Education')
WHERE subject_specialty IS NOT NULL
  AND subject_specialty LIKE '%PE%'
  AND subject_specialty NOT LIKE '%Physical Education%';

-- Also normalize school_jobs age_groups if they exist
UPDATE school_jobs
SET age_groups = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(age_groups, 'kindergarten', 'Kindergarten'),
                'primary', 'Primary'
            ),
            'middle_school', 'Middle School'
        ),
        'high_school', 'High School'
    ),
    'university', 'University'
)
WHERE age_groups IS NOT NULL
  AND (
    age_groups ILIKE '%kindergarten%'
    OR age_groups ILIKE '%primary%'
    OR age_groups ILIKE '%middle_school%'
    OR age_groups ILIKE '%high_school%'
    OR age_groups ILIKE '%university%'
  );

-- Normalize subjects in school_jobs: PE -> Physical Education
UPDATE school_jobs
SET subjects = REPLACE(subjects, 'PE', 'Physical Education')
WHERE subjects IS NOT NULL
  AND subjects LIKE '%PE%'
  AND subjects NOT LIKE '%Physical Education%';
