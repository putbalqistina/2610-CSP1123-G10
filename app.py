from flask import Flask, render_template, request, redirect, url_for
import os
app = Flask(__name__)


app.config['UPLOAD_FOLDER'] = 'static/uploads'
# dummy subjects
subjects = [
    {"code": "CSP1123", "name": "Mini IT Project"},
    {"code": "CDS1114", "name": "Digital Systems"},
    {"code": "CMT1134", "name": "Mathematics III"},
    {"code": "LCT1113", "name": "Critical Thinking"}
]

assignment_store = {
    "Proposal": {
        "description": "This is assignment description",
        "comments": ["my part - done", "need to finish before 20/4"],
        "attachment": None
    }
}
# dummy assignments
assignments_data = {
    "CSP1123": ["Proposal", "Final Report"],
    "CDS1114": ["Lab 1", "Lab 2"],
    "CMT1134": ["Quiz 1", "Test 2"],
    "LCT1113": ["Blended Learning Week 2", "20% Presentation", "Debate Points"]
}



@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', subjects=subjects)


@app.route('/subject/<code>')
def subject(code):
    assignments = assignments_data.get(code, [])
    return render_template('subject.html', code=code, assignments=assignments)


@app.route('/add-assignment')
def add_assignment():
    return "<h1>Page Not Found (UI coming soon)</h1>"


@app.route('/assignment/<title>', methods=["GET", "POST"])
def assignment(title):

    if title not in assignment_store:
        assignment_store[title] = {
            "description": "",
            "comments": [],
            "attachment": None
        }

    data = assignment_store[title]

    if request.method == "POST":

        # update description
        new_desc = request.form.get("description")
        if new_desc:
            data["description"] = new_desc

        # add comment
        new_comment = request.form.get("comment")
        if new_comment:
            data["comments"].append(new_comment)

        # file upload
        file = request.files.get("file")
        if file and file.filename != "":
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            data["attachment"] = file.filename

        return redirect(url_for("assignment", title=title))

    return render_template(
        "assignment.html",
        title=title,
        description=data["description"],
        comments=data["comments"],
        attachment=data["attachment"]
    )


if __name__ == '__main__':
    app.run(debug=True)