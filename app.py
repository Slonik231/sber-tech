from flask import Flask, request, render_template, send_file, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import sessionmaker
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
db = SQLAlchemy(app)

# Create the sessionmaker inside the app context
with app.app_context():
    Session = sessionmaker(bind=db.engine)

# Модель для проектов
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    employees = db.Column(db.Integer, nullable=False)
    tasks = db.Column(db.Integer, nullable=False)
    effort = db.Column(db.Float, nullable=False)
    emplcost = db.Column(db.Float, nullable=False)
    percent = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False)
    perspective = db.Column(db.Boolean, default=False)
    employee_reports = db.relationship('EmployeeReport', backref='project', lazy=True)

    def calculate_cost(self):
        total_cost = 0.0
        for employee_report in self.employee_reports:
            total_cost += employee_report.tasks * employee_report.effort * employee_report.percent * employee_report.emplcost
        return total_cost

# Модель для отчетов по сотрудникам
class EmployeeReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    tasks = db.Column(db.Integer, nullable=False)
    effort = db.Column(db.Float, nullable=False)
    emplcost = db.Column(db.Float, nullable=False)
    percent = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

# Веса для каждого параметра
weights = {
    'employees': 0.2,
    'effort': 0.2,
    'emplcost': -0.4,
    'percent': -0.9
}

def evaluate_project(project):
    total_tasks = sum([employee_report.tasks for employee_report in project.employee_reports])
    total_effort = sum([employee_report.effort for employee_report in project.employee_reports])
    total_emplcost = sum([employee_report.emplcost for employee_report in project.employee_reports])
    total_percent = sum([employee_report.percent for employee_report in project.employee_reports]) / len(project.employee_reports)

    score = weights['employees'] * project.employees + weights['effort'] * total_effort + weights['emplcost'] * total_emplcost + weights['percent'] * total_percent
    perspective = score >= -580
    return perspective

@app.route('/optimize/<int:project_id>', methods=['POST'])
def optimize(project_id):
    project = Project.query.get(project_id)
    perspective = evaluate_project(project)

    while not perspective:
        for employee_report in project.employee_reports:
            # Увеличиваем параметр 'percent' на 0.0003
            employee_report.percent = min(employee_report.percent + 0.00003, 1.0)
            # Уменьшаем параметры 'effort' и 'emplcost' на 0.1, но не допускаем слишком маленьких значений 'effort'
            employee_report.effort = max(employee_report.effort - 0.1, 10)
            employee_report.emplcost = max(employee_report.emplcost - 0.1, 0.1)

        db.session.commit()  # Сохраняем изменения в базе данных

        perspective = evaluate_project(project)
        project.perspective = perspective

        # Вычисляем и сохраняем новую стоимость проекта
        project.cost = project.calculate_cost()
        db.session.commit()  # Обновляем значение перспективности проекта и стоимость в базе данных

    return redirect('/')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        project_name = request.form.get('project_name')
        employees = int(request.form.get('employees'))

        project = Project(name=project_name, employees=employees, tasks=0, effort=0.0, emplcost=0.0, percent=0.0, cost=0.0)

        for i in range(employees):
            tasks = request.form.get(f'employee_{i}_tasks')
            effort = request.form.get(f'employee_{i}_effort')
            emplcost = request.form.get(f'employee_{i}_emplcost')
            percent = request.form.get(f'employee_{i}_percent')
            if tasks and effort and emplcost and percent:
                employee_report = EmployeeReport(tasks=int(tasks), effort=float(effort), emplcost=float(emplcost), percent=float(percent))
                project.employee_reports.append(employee_report)

        total_tasks = sum([employee_report.tasks for employee_report in project.employee_reports])
        project.tasks = total_tasks

        project.cost = project.calculate_cost()
        perspective = evaluate_project(project)
        project.perspective = perspective

        db.session.add(project)
        db.session.commit()

    projects = Project.query.all()
    return render_template('index.html', projects=projects)

@app.route('/project/<int:project_id>', methods=['GET', 'POST'])
def project(project_id):
    project = Project.query.get(project_id)
    if request.method == 'POST' and 'optimize' in request.form:
        perspective = evaluate_project(project)
        project.perspective = perspective

        while not perspective:
            for employee_report in project.employee_reports:
                # Увеличиваем параметр 'percent' на 0.0003
                employee_report.percent = min(employee_report.percent + 0.0003, 1.0)
                # Уменьшаем параметры 'effort' и 'emplcost' на 0.1, но не допускаем слишком маленьких значений 'effort'
                employee_report.effort = max(employee_report.effort - 0.1, 10)
                employee_report.emplcost = max(employee_report.emplcost - 0.1, 0.1)

            db.session.commit()  # Сохраняем изменения в базе данных

            perspective = evaluate_project(project)
            project.perspective = perspective

            # Вычисляем и сохраняем новую стоимость проекта
            project.cost = project.calculate_cost()
            db.session.commit()  # Обновляем значение перспективности проекта и стоимость в базе данных

    return render_template('project.html', project=project)

@app.route('/download/<int:project_id>', methods=['GET'])
def download(project_id):
    project = Project.query.get(project_id)
    total_tasks = sum([employee_report.tasks for employee_report in project.employee_reports])
    project_data = {
        'name': project.name,
        'employees': project.employees,
        'tasks': total_tasks,
        'cost': project.cost,
        'perspective': project.perspective,
        'employee_reports': []
    }

    for employee_report in project.employee_reports:
        employee_report_data = {
            'tasks': employee_report.tasks,
            'effort': employee_report.effort,
            'emplcost': employee_report.emplcost,
            'percent': employee_report.percent
        }
        project_data['employee_reports'].append(employee_report_data)

    project_data['cost'] = project.cost

    filename = f'{project.name}_report.json'
    with open(filename, 'w') as file:
        json.dump(project_data, file, indent=4)

    return send_file(filename, as_attachment=True)

@app.route('/download/all', methods=['GET'])
def download_all():
    projects = Project.query.all()
    all_projects_data = []

    for project in projects:
        total_tasks = sum([employee_report.tasks for employee_report in project.employee_reports])
        project_data = {
            'name': project.name,
            'employees': project.employees,
            'tasks': total_tasks,
            'cost': project.cost,
            'perspective': project.perspective,
            'employee_reports': []
        }

        for employee_report in project.employee_reports:
            employee_report_data = {
                'tasks': employee_report.tasks,
                'effort': employee_report.effort,
                'emplcost': employee_report.emplcost,
                'percent': employee_report.percent
            }
            project_data['employee_reports'].append(employee_report_data)

        all_projects_data.append(project_data)

    filename = 'all_projects_report.json'
    with open(filename, 'w') as file:
        json.dump(all_projects_data, file, indent=4)

    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
