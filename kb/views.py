"""The review app: an overview per topic, and one page per question shown as a chat.

Every request reads kb.xlsx fresh, and every save writes it straight back.
"""

from datetime import datetime

from django.conf import settings
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from kb import project, workbook

REASONS = ("made up", "less relevant", "other")


def load():
    """The project, the workbook, its stamp, and all its questions."""
    proj = project.load(settings.PROJECT_DIR)
    wb, stamp = workbook.open_kb(proj.kb_path)
    return proj, wb, stamp, workbook.questions(wb, proj)


def overview(request):
    """Per topic: how many questions, answered, accepted, to revise, rejected, still to review."""
    _, wb, _, rows = load()
    topics = []
    for sheet in workbook.topic_sheets(wb):
        mine = [q for q in rows if q["_sheet"] == sheet]
        answered = [q for q in mine if q["answer"]]
        counts = {status: sum(q["status"] == status for q in mine) for status in workbook.STATUSES}
        first = next((q["id"] for q in answered if not q["status"]), None) or (mine[0]["id"] if mine else None)
        topics.append({"name": sheet, "questions": len(mine), "answered": len(answered), "counts": counts,
                       "open": sum(1 for q in answered if not q["status"]), "first": first})
    return render(request, "kb/overview.html", {"topics": topics, "reviewer": request.COOKIES.get("reviewer", "")})


@require_POST
def reviewer(request):
    """Remember the reviewer's name in a cookie; it is saved with every review."""
    response = redirect("overview")
    response.set_cookie("reviewer", request.POST.get("reviewer", "").strip()[:80], max_age=365 * 24 * 3600, samesite="Strict")
    return response


def question(request, qid):
    """One question as a chat, with its simpler answer, variants, evidence and review form; POST saves."""
    proj, wb, stamp, rows = load()
    q = next((r for r in rows if r["id"] == qid), None)
    if q is None:
        raise Http404(f"There is no question {qid} in kb.xlsx.")
    if request.method == "POST":
        return save(request, proj, wb, stamp, rows, q)
    sources = {r["ID"]: r for r in workbook.records(wb[workbook.SOURCES])}
    evidence = [{**r, "row": r["_row"], "source": sources.get(r["Source"], {})}
                for r in workbook.records(wb[workbook.EVIDENCE]) if r["Question"] == qid]
    topic = [r for r in rows if r["_sheet"] == q["_sheet"]]
    position = rows.index(q)
    return render(request, "kb/question.html", {
        "q": q, "topic": q["_sheet"], "labels": proj.topic_columns(), "evidence": evidence, "reasons": REASONS,
        "statuses": workbook.STATUSES, "number": topic.index(q) + 1, "total": len(topic),
        "variants": [q[f"question_variant_{n}"] for n in range(1, proj.question_variants + 1) if q[f"question_variant_{n}"]],
        "previous": rows[position - 1]["id"] if position > 0 else None,
        "next": rows[position + 1]["id"] if position + 1 < len(rows) else None,
        "reviewer": request.COOKIES.get("reviewer", ""),
    })


def save(request, proj, wb, stamp, rows, q):
    """Write status, comment, final answer and removed sources to kb.xlsx, then show this or the next question.

    When the file is open in Excel or was changed by someone else, nothing is written and the
    reviewer is told why.
    """
    status = request.POST.get("status", "")
    if status not in ("", *workbook.STATUSES):
        return HttpResponseBadRequest("Unknown status.")
    labels, sheet = proj.topic_columns(), wb[q["_sheet"]]
    values = {"status": status or None,
              "comment": request.POST.get("comment", "").strip() or None,
              "final_answer": request.POST.get("final_answer", "").strip() or None,
              "reviewer": request.COOKIES.get("reviewer") or None,
              "reviewed_at": f"{datetime.now():%Y-%m-%d %H:%M}"}
    for key, value in values.items():
        workbook.put(sheet, q["_row"], labels[key], value)
    evidence = wb[workbook.EVIDENCE]
    for r in workbook.records(evidence):
        if r["Question"] == q["id"]:
            removed = f"remove_{r['_row']}" in request.POST
            workbook.put(evidence, r["_row"], "Removed", "yes" if removed else None)
            workbook.put(evidence, r["_row"], "Reason", request.POST.get(f"reason_{r['_row']}") if removed else None)
    try:
        workbook.save(wb, proj.kb_path, stamp, proj)
    except PermissionError:
        return render(request, "kb/error.html", {"error": "kb.xlsx is open in Excel. Close it there, then save again."}, status=409)
    except workbook.ChangedOnDisk as error:
        return render(request, "kb/error.html", {"error": str(error)}, status=409)
    following = next((r for r in rows[rows.index(q) + 1:] if r["answer"] and not r["status"]), None)
    if "next" in request.POST and following:
        return redirect("question", qid=following["id"])
    return redirect("question", qid=q["id"])
