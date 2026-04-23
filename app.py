from flask import Flask, render_template

app = Flask(__name__)

# dummy subjects
subjects = [
    {"code": "CSP1123", "name": "Mini IT Project"},
    {"code": "CDS1114", "name": "Digital Systems"},
    {"code": "CMT1134", "name": "Mathematics III"},
    {"code": "LCT1113", "name": "Critical Thinking"}
]

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

@app.route('/assignment/<title>')
def assignment(title):

    # dummy data dulu
    description = "This is assignment description"
    comments = ["my part - done", "need to finish before 20/4"]
    attachment = "sample.png"

    return render_template(
        'assignment.html',
        title=title,
        description=description,
        comments=comments,
        attachment=attachment
    )


if __name__ == '__main__':
    app.run(debug=True)