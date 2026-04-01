from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy.orm import class_mapper, ColumnProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy import Integer
import os
from werkzeug.security import generate_password_hash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_cors import CORS
import smtplib
import random
import base64
import uuid
from flask_restful import Api
from datetime import datetime, timedelta
from textblob import TextBlob

# PostgreSQL - no extra import needed

app = Flask(__name__)
CORS(app)

# ✅ Reads from Railway environment variable (DATABASE_URL)
db_url = os.environ.get('DATABASE_URL', 'mysql://root:XCzWFRlAgCigdQYEfFiCsOFvXSSUfSew@interchange.proxy.rlwy.net:21728/railway')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'perioguard-secret')
bcrypt = Bcrypt(app)

db = SQLAlchemy(app)

class DoctorDetails(db.Model):
    __tablename__ = 'doctor_details'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    number = db.Column(db.String(15), nullable=False)
    license = db.Column(db.String(100), nullable=False)
    speciality = db.Column(db.String(100))
    hospital_name = db.Column(db.String(150))
    password = db.Column(db.String(255), nullable=False)

@app.route('/register_doctor', methods=['POST'])
def register_doctor():
    data = request.get_json()

    name = data.get('name')
    email = data.get('email')
    number = data.get('number')
    license = data.get('license')
    speciality = data.get('speciality')
    hospital_name = data.get('hospital_name')
    password = data.get('password')

    if not all([name, email, number, license, password]):
        return jsonify({"error": "Missing required fields"}), 400

    existing_user = DoctorDetails.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Email already registered"}), 409

    hashed_password = generate_password_hash(password)

    new_doctor = DoctorDetails(
        name=name,
        email=email,
        number=number,
        license=license,
        speciality=speciality,
        hospital_name=hospital_name,
        password=hashed_password
    )

    db.session.add(new_doctor)
    db.session.commit()

    return jsonify({
        "message": "Doctor registered successfully",
        "doctor_id": new_doctor.id
    }), 201

@app.route('/login_doctor', methods=['POST'])
def login_doctor():
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    doctor = DoctorDetails.query.filter_by(email=email).first()

    if not doctor:
        return jsonify({"error": "Invalid email or password"}), 401

    if not check_password_hash(doctor.password, password):
        return jsonify({"error": "Invalid email or password"}), 401

    login_entry = Active(email=email, login_time=datetime.utcnow())
    db.session.add(login_entry)
    db.session.commit()

    return jsonify({
        "message": "Login successful",
        "doctor": {
            "id": doctor.id,
            "name": doctor.name,
            "email": doctor.email,
            "speciality": doctor.speciality,
            "hospital_name": doctor.hospital_name
        }
    }), 200

class Active(db.Model):
    __tablename__ = 'active'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(150), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/get_profile', methods=['GET'])
def get_profile():
    latest = Active.query.order_by(Active.login_time.desc()).first()

    if not latest:
        return jsonify({"error": "No active user"}), 404

    doctor = DoctorDetails.query.filter_by(email=latest.email).first()

    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    return jsonify({
        "id": doctor.id,
        "name": doctor.name,
        "email": doctor.email,
        "number": doctor.number,
        "license": doctor.license,
        "speciality": doctor.speciality,
        "hospital_name": doctor.hospital_name
    }), 200

@app.route('/update_profile', methods=['PUT'])
def update_profile():
    data = request.get_json()

    email = data.get('email')

    doctor = DoctorDetails.query.filter_by(email=email).first()

    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    doctor.name = data.get('name', doctor.name)
    doctor.number = data.get('number', doctor.number)
    doctor.speciality = data.get('speciality', doctor.speciality)
    doctor.hospital_name = data.get('hospital_name', doctor.hospital_name)

    db.session.commit()

    return jsonify({"message": "Profile updated successfully"}), 200

class PatientLogin(db.Model):
    __tablename__ = 'patient_login'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)

@app.route('/patient_register', methods=['POST'])
def patient_register():
    data = request.get_json()

    patient_id = data.get('patient_id')
    password = data.get('password')

    if not patient_id or not password:
        return jsonify({"error": "patient_id and password are required"}), 400

    existing = PatientLogin.query.filter_by(patient_id=patient_id).first()
    if existing:
        return jsonify({"error": "Patient ID already exists"}), 409

    hashed_password = generate_password_hash(password)

    new_patient = PatientLogin(
        patient_id=patient_id,
        password=hashed_password
    )

    db.session.add(new_patient)
    db.session.commit()

    return jsonify({
        "message": "Patient registered successfully",
        "patient_id": patient_id
    }), 201

class PatientActive(db.Model):
    __tablename__ = 'patient_active'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.String(100), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/patient_login', methods=['POST'])
def patient_login():
    data = request.get_json()

    patient_id = data.get('patient_id')
    password = data.get('password')

    if not patient_id or not password:
        return jsonify({"error": "patient_id and password are required"}), 400

    patient = PatientLogin.query.filter_by(patient_id=patient_id).first()

    if not patient:
        return jsonify({"error": "Invalid patient ID or password"}), 401

    if not check_password_hash(patient.password, password):
        return jsonify({"error": "Invalid patient ID or password"}), 401

    login_entry = PatientActive(
        patient_id=patient_id,
        login_time=datetime.utcnow()
    )
    db.session.add(login_entry)
    db.session.commit()

    return jsonify({
        "message": "Login successful",
        "patient_id": patient.patient_id
    }), 200


@app.route('/get_patient_profile', methods=['GET'])
def get_patient_profile():
    latest = PatientActive.query.order_by(PatientActive.login_time.desc()).first()

    if not latest:
        return jsonify({"error": "No active patient"}), 404

    profile = PatientProfile.query.filter_by(patient_id=latest.patient_id).first()

    if not profile:
        return jsonify({"message": "No profile found"}), 200

    return jsonify({
        "patient_id": profile.patient_id,
        "name": profile.name,
        "age": profile.age,
        "gender": profile.gender,
        "phone": profile.phone,
        "address": profile.address
    }), 200

class PatientProfile(db.Model):
    __tablename__ = 'patient_profile'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))

@app.route('/update_patient_profile', methods=['POST'])
def update_patient_profile():
    data = request.get_json()

    latest = PatientActive.query.order_by(PatientActive.login_time.desc()).first()

    if not latest:
        return jsonify({"error": "No active patient"}), 404

    patient_id = latest.patient_id

    profile = PatientProfile.query.filter_by(patient_id=patient_id).first()

    if profile:
        profile.name = data.get('name')
        profile.age = data.get('age')
        profile.gender = data.get('gender')
        profile.phone = data.get('phone')
        profile.address = data.get('address')
    else:
        profile = PatientProfile(
            patient_id=patient_id,
            name=data.get('name'),
            age=data.get('age'),
            gender=data.get('gender'),
            phone=data.get('phone'),
            address=data.get('address')
        )
        db.session.add(profile)

    db.session.commit()

    return jsonify({"message": "Profile saved"}), 200

class PatientAnalysis(db.Model):
    __tablename__ = 'patient_analysis'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(100))
    bone_loss = db.Column(db.String(50))
    bone_loss_mm = db.Column(db.Float)
    inflammation = db.Column(db.String(50))
    severity_percent = db.Column(db.Integer)
    severity_label = db.Column(db.String(50))
    condition_name = db.Column(db.String(100))
    alert = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime)


@app.route('/save_analysis', methods=['POST'])
def save_analysis():
    data = request.get_json()

    latest = PatientActive.query.order_by(PatientActive.login_time.desc()).first()

    if not latest:
        return jsonify({"error": "No active patient"}), 404

    patient_id = latest.patient_id

    analysis = PatientAnalysis(
        patient_id=patient_id,
        bone_loss=data['bone_loss']['value'],
        bone_loss_mm=data['bone_loss']['raw_mm'],
        inflammation=data['inflammation']['value'],
        severity_percent=data['severity']['percent'],
        severity_label=data['severity']['label'],
        condition_name=data['condition'],
        alert=data['alert']
    )

    db.session.add(analysis)
    db.session.commit()

    return jsonify({"message": "Saved"}), 200

@app.route('/get_latest_analysis', methods=['GET'])
def get_latest_analysis():
    latest_patient = PatientActive.query.order_by(PatientActive.login_time.desc()).first()

    if not latest_patient:
        return jsonify({"error": "No active patient"}), 404

    analysis = PatientAnalysis.query \
        .filter_by(patient_id=latest_patient.patient_id) \
        .order_by(PatientAnalysis.id.desc()) \
        .first()

    if not analysis:
        return jsonify({"error": "No analysis found"}), 404

    return jsonify({
        "bone_loss": {
            "value": analysis.bone_loss,
            "subtitle": "",
            "raw_mm": analysis.bone_loss_mm
        },
        "inflammation": {
            "value": analysis.inflammation,
            "subtitle": ""
        },
        "severity": {
            "percent": analysis.severity_percent,
            "label": analysis.severity_label,
            "description": ""
        },
        "condition": analysis.condition_name,
        "alert": analysis.alert
    }), 200

class HealthHistory(db.Model):
    __tablename__ = 'health_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position = db.Column(db.String(100))
    placement_date = db.Column(db.Date)
    brand = db.Column(db.String(100))
    history = db.Column(db.Text)
    brushing = db.Column(db.String(50))
    flossing = db.Column(db.String(50))
    symptoms = db.Column(db.JSON)
    severity = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/add-health-history', methods=['POST'])
def add_health_history():
    try:
        data = request.get_json()

        new_record = HealthHistory(
            position=data.get('position'),
            placement_date=datetime.strptime(data.get('placement_date'), '%Y-%m-%d') if data.get('placement_date') else None,
            brand=data.get('brand'),
            history=data.get('history'),
            brushing=data.get('brushing'),
            flossing=data.get('flossing'),
            symptoms=data.get('symptoms'),
            severity=data.get('severity')
        )

        db.session.add(new_record)
        db.session.commit()

        return jsonify({"message": "Saved successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


class Appointment(db.Model):
    __tablename__ = 'appointments'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_name = db.Column(db.String(100), nullable=False)
    phone        = db.Column(db.String(20))
    date         = db.Column(db.Date, nullable=False)
    time_slot    = db.Column(db.String(20), nullable=False)
    reason       = db.Column(db.String(200))
    status       = db.Column(db.String(20), default='confirmed')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/book-appointment', methods=['POST'])
def book_appointment():
    try:
        data = request.get_json()

        required = ['patient_name', 'date', 'time_slot']
        for field in required:
            if not data.get(field):
                return jsonify({"error": f"'{field}' is required"}), 400

        appointment = Appointment(
            patient_name = data.get('patient_name'),
            phone        = data.get('phone', ''),
            date         = datetime.strptime(data['date'], '%Y-%m-%d').date(),
            time_slot    = data.get('time_slot'),
            reason       = data.get('reason', 'Routine implant check'),
            status       = 'confirmed',
        )

        db.session.add(appointment)
        db.session.commit()

        return jsonify({
            "message":        "Appointment booked successfully",
            "appointment_id": appointment.id,
            "date":           str(appointment.date),
            "time_slot":      appointment.time_slot,
            "status":         appointment.status,
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/get-appointments', methods=['GET'])
def get_appointments():
    try:
        appointments = Appointment.query.order_by(Appointment.date.asc()).all()
        result = [{
            "id":           a.id,
            "patient_name": a.patient_name,
            "phone":        a.phone,
            "date":         str(a.date),
            "time_slot":    a.time_slot,
            "reason":       a.reason,
            "status":       a.status,
            "created_at":   str(a.created_at),
        } for a in appointments]
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-next-appointment', methods=['GET'])
def get_next_appointment():
    try:
        from datetime import date
        appt = Appointment.query.filter(
            Appointment.date >= date.today()
        ).order_by(Appointment.date.asc()).first()

        if not appt:
            return jsonify({"found": False}), 200

        days_remaining = (appt.date - date.today()).days

        return jsonify({
            "found": True,
            "date": str(appt.date),
            "time_slot": appt.time_slot,
            "days_remaining": days_remaining,
            "status": appt.status,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_all_patients_latest_analysis', methods=['GET'])
def get_all_patients_latest_analysis():
    try:
        patients = PatientProfile.query.all()
        result = []

        for patient in patients:
            analysis = PatientAnalysis.query \
                .filter_by(patient_id=patient.patient_id) \
                .order_by(PatientAnalysis.id.desc()) \
                .first()

            analysis_data = None
            if analysis:
                analysis_data = {
                    "bone_loss":        getattr(analysis, 'bone_loss', '--'),
                    "bone_loss_mm":     getattr(analysis, 'bone_loss_mm', 0),
                    "inflammation":     getattr(analysis, 'inflammation', '--'),
                    "severity_percent": getattr(analysis, 'severity_percent', 0),
                    "severity_label":   getattr(analysis, 'severity_label', '--'),
                    "condition":        getattr(analysis, 'condition_name', 'No Analysis'),
                    "alert":            getattr(analysis, 'alert', False),
                    "date":             str(analysis.created_at.date()) if analysis.created_at else '--',
                }

            result.append({
                "patient_id":   patient.patient_id,
                "patient_name": patient.name,
                "analysis":     analysis_data,
            })

        return jsonify(result), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/get_dashboard_stats', methods=['GET'])
def get_dashboard_stats():
    try:
        total_patients = PatientProfile.query.count()

        high_risk = PatientAnalysis.query.filter(
            db.or_(
                PatientAnalysis.alert == True,
                PatientAnalysis.severity_label == 'Action Required'
            )
        ).count()

        today = datetime.utcnow().date()
        scans_today = PatientAnalysis.query.filter(
            db.func.date(PatientAnalysis.created_at) == today
        ).count()

        urgent_alerts = PatientAnalysis.query.filter(
            PatientAnalysis.alert == True
        ).count()

        subquery = db.session.query(
            PatientAnalysis.patient_id,
            db.func.max(PatientAnalysis.id).label('max_id')
        ).group_by(PatientAnalysis.patient_id).subquery()

        recent_analyses = db.session.query(PatientAnalysis).join(
            subquery, PatientAnalysis.id == subquery.c.max_id
        ).order_by(PatientAnalysis.created_at.desc()).limit(3).all()

        recent_scans = []
        for a in recent_analyses:
            profile = PatientProfile.query.filter_by(patient_id=a.patient_id).first()
            diff = (datetime.utcnow() - a.created_at).total_seconds() if a.created_at else 0
            hours = int(diff // 3600)
            days = int(diff // 86400)
            time_ago = f'{days}d ago' if days >= 1 else f'{hours}h ago' if hours >= 1 else 'Just now'

            recent_scans.append({
                'patient_id':   a.patient_id,
                'patient_name': profile.name if profile else 'Unknown',
                'time':         time_ago,
                'analysis': {
                    'bone_loss':          a.bone_loss or '--',
                    'bone_loss_mm':       a.bone_loss_mm or 0,
                    'inflammation':       a.inflammation or '--',
                    'severity_percent':   a.severity_percent or 0,
                    'severity_label':     a.severity_label or '--',
                    'condition':          a.condition_name or 'No Analysis',
                    'alert':              a.alert or False,
                    'date':               str(a.created_at.date()) if a.created_at else '--',
                }
            })

        return jsonify({
            'total_patients': total_patients,
            'high_risk':      high_risk,
            'scans_today':    scans_today,
            'recent_scans':   recent_scans,
            'urgent_alerts':  urgent_alerts,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
