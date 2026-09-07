TOTAL_CHAPTERS = 5


def project_progress_percent(project):
    approved = sum(1 for s in project.submissions if s.status == "approved")
    return round((approved / TOTAL_CHAPTERS) * 100)


def project_chapter_breakdown(project):
    """Returns the latest submission status per chapter number (1..TOTAL_CHAPTERS)."""
    latest_by_chapter = {}
    for s in project.submissions:
        existing = latest_by_chapter.get(s.chapter_number)
        if existing is None or s.submitted_at > existing.submitted_at:
            latest_by_chapter[s.chapter_number] = s

    breakdown = []
    for ch in range(1, TOTAL_CHAPTERS + 1):
        submission = latest_by_chapter.get(ch)
        breakdown.append({
            "chapter_number": ch,
            "status": submission.status if submission else "not_submitted",
            "submission": submission,
        })
    return breakdown


def submission_counts(project):
    counts = {"total": TOTAL_CHAPTERS, "pending": 0, "approved": 0, "rejected": 0}
    for s in project.submissions:
        if s.status in counts:
            counts[s.status] += 1
    return counts
