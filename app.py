import random, os
import smtplib
import cloudinary
from xhtml2pdf import pisa
from io import BytesIO
from dotenv import load_dotenv
from decimal import Decimal
from datetime import datetime
from sqlalchemy import func
from email.mime.text import MIMEText
from flask import Flask, request, render_template, abort, redirect, flash, url_for, make_response, jsonify, session
from flask_login import current_user, login_required, LoginManager, login_user, logout_user
from models import db, ServiceProvider,Appointment,GadgetType, User


app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv('secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] =  os.getenv('url_db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = r'C:\Users\Pc\Desktop\PROJECTS\Project\uploads'

cloudinary.config(
  cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
  api_key=os.getenv('CLOUDINARY_API_KEY'),
  api_secret=os.getenv('CLOUDINARY_API_SECRET'),
  secure=True
)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
# login_manager.login_view = 'login'

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/user/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Unauthorized'}), 401
    return redirect(url_for('login', next=request.url))

def send_verification_email(to_email, code):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "no.reply.TestingBasedEmail@gmail.com"
    sender_password = "wcezljjvlhfibzxj"  

    subject = "OTP for E-Mail verification"
    body = f"Your OTP for E-Mail verification is {code} valid only for 2 minutes. Do not share with anyone."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, to_email, msg.as_string())
    server.quit()


@app.route('/')
def landing():
    return render_template('landingPage.html')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/landing_profile')
def landing_profile():
    return render_template('profile.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()  
    session.clear()  
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing'))

@app.route('/check_email2', methods=['POST'])
def check_email2():
    data = request.get_json()
    email = data.get('email', '').lower()
    user = User.query.filter_by(username=email).first()

    if user:
        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['otp_email'] = email
        send_verification_email(email, otp)  
        return jsonify({'exists': True})

    return jsonify({'exists': False})



@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email', '').lower()
    otp_submitted = data.get('otp')

    otp_saved = session.get('otp')
    otp_email = session.get('otp_email')

    if otp_submitted == otp_saved and email == otp_email:
        user = User.query.filter_by(username=email).first()
        if user:
            login_user(user)
            session.pop('otp')
            session.pop('otp_email')
            return jsonify({'success': True})
        if not user:
            flash('User not found. Please sign up.', 'warning')
            return redirect(url_for('signup', email=email))
    return jsonify({'success': False})


@app.route('/login')
def login():
    email = request.args.get('email', '').strip().lower()
    gadget = request.args.get('gadget', '')

    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('login_form', gadget=gadget))  

    user = User.query.filter_by(username=email).first()

    if not user:
        flash('User not found. Please sign up.', 'warning')
        return redirect(url_for('signup', email=email))

    return redirect(url_for('show_providers', gadget=gadget))



@app.route('/login_form', methods=['GET'])
def login_form():
    gadget = request.args.get('gadget', '')
    if current_user.is_authenticated:
        return redirect(url_for('show_providers', gadget=gadget))
    return render_template('user_login.html')



@app.route('/providers1')
@login_required
def providers1():
    user_lat = request.args.get('lat', type=float)
    user_lon = request.args.get('lon', type=float)
    gadget = request.args.get('gadget', default='')

    if user_lat is None or user_lon is None:
        flash("Location info is required to see nearby providers.", "warning")
        return redirect(url_for('some_page_to_get_location'))

    providers = ServiceProvider.query.filter_by(approved=True).all()

    return render_template('providers.html', providers=providers, gadget=gadget)



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    email_prefill = request.args.get('email', '').strip().lower()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobile_number', '').strip()

        if User.query.filter_by(username=email).first():
            flash('Email already registered. Please log in.', 'warning')
            return redirect(url_for('login', email=email))

        new_user = User(username=email, mobile_number=mobile)
        db.session.add(new_user)
        db.session.commit()

        
        flash('Account created and logged in.', 'success')
        return redirect(url_for('provider_profile'))

    return render_template('signup.html', email=email_prefill)



@app.route('/provider/verify_email', methods=['POST'])
def verify_email():
    username = request.form.get('username')  
    if not username:
        return jsonify({"error": "Username is required"}), 400

    provider = ServiceProvider.query.filter_by(username=username).first()

    if not provider:
        flash("Provider not found", "error")
        return redirect(url_for('verify_email'))

    code = str(random.randint(100000, 999999))
    session['verification_code'] = code
    session['username'] = username

    send_verification_email(provider.email, code)

    flash("Verification code sent to your email.", "info")
    return render_template('verify.html')



@app.route('/providers', methods=['GET', 'POST'])
def show_providers():
    gadget = request.args.get('gadget', '')
    providers = ServiceProvider.query.filter_by(approved=True).all()
    return render_template('main.html', providers=providers, gadget = gadget)


@app.route('/provider/<int:provider_id>')
def provider_profile(provider_id):
    provider = db.session.get(ServiceProvider, provider_id)
    gadget = request.args.get('gadget', '')
    if not provider:
        abort(404)
    return render_template('providr_profile.html', provider=provider, gadget_type=gadget)


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    cloudinary_url = cloudinary.CloudinaryImage(filename).build_url(secure=True)
    return redirect(cloudinary_url)


@app.route('/provider/<int:provider_id>', methods=['GET', 'POST'])
@login_required
def provider_profile1(provider_id):
    provider = ServiceProvider.query.get_or_404(provider_id)
    gadget = request.args.get('gadget', '').lower()
   
    
    if request.method == 'POST':
        purchase_date = request.form.get('purchase_date')
        problem_description = request.form.get('problem_description')
        preferred_time = request.form.get('preferred_time')
        gadget_type_name = request.form.get('gadget_type') or gadget
        gadget_type = GadgetType.query.filter(func.lower(GadgetType.name) == gadget_type_name).first()

        if not gadget_type:
            flash('Invalid gadget type selected.', 'danger')
            return redirect(request.url)

        appointment = Appointment(
            user_id=current_user.id,
            provider_id=provider.id,
            gadget_type_id=gadget_type.id,
            purchase_date=datetime.strptime(purchase_date, '%Y-%m-%d'),
            problem_description=problem_description,
            preferred_time=datetime.strptime(preferred_time, '%Y-%m-%dT%H:%M'),
            status='New'
        )

        db.session.add(appointment)
        db.session.commit()
        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('show_providers', gadget=gadget))

    return redirect(url_for('show_providers', provider=provider, gadget=gadget))



@app.route('/user/appointments', methods=['GET'])
@login_required
def user_appointments():
    appointments = Appointment.query.filter_by(user_id=current_user.id).all()
    grouped = {
        "New": [],
        "Pending": [],           
        "Completed": [],
        "Cancelled": [],
        "Rescheduled": []
    }

    for a in appointments:
        item = {
            "id": a.id,
            "model": a.model,
            "preferred_time": a.preferred_time.strftime('%Y-%m-%d %H:%M'),
            "status": a.status,
            "description": a.problem_description,
            "cancel_reason": a.cancel_reason,
            "r_time": a.reschedule_time.strftime('%Y-%m-%d %H:%M') if a.reschedule_time else None
        }

        if a.status == 'Completed':
            item['has_reviewed'] = bool(a.rating or a.comment)
            item["payment_status"]= bool(a.payment_status)

        if a.status in ['Pending', 'Pending_Rescheduled']:
            grouped['Pending'].append(item)
        elif a.status in grouped:
            grouped[a.status].append(item)
        else:
            # fallback in case of unexpected status
            grouped['New'].append(item)

    return jsonify(grouped)



@app.route('/appointments/<int:appointment_id>/review', methods=['POST'])
@login_required
def submit_review(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=current_user.id).first()

    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    if appointment.status != 'Completed':
        return jsonify({'error': 'Only completed appointments can be reviewed'}), 400

    data = request.get_json()
    rating = data.get('rating')
    comment = data.get('comment')

    if not rating:
        return jsonify({'error': 'Rating is required'}), 400

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError()
    except ValueError:
        return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400

    appointment.rating = rating
    appointment.comment = comment
    db.session.commit()

    return jsonify({'message': 'Review submitted successfully'})

@app.route('/provider/<int:provider_id>/average_rating')
def get_average_rating(provider_id):
    avg_rating = db.session.query(
        db.func.avg(Appointment.rating)
    ).filter(
        Appointment.provider_id == provider_id,
        Appointment.status == 'Completed',
        Appointment.rating.isnot(None)
    ).scalar()

    if avg_rating is None:
        avg_rating = 0.0
    elif isinstance(avg_rating, Decimal):
        avg_rating = float(avg_rating)

    return jsonify({'average_rating': avg_rating})



@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        if not full_name or not email or not phone:
            flash('All fields are required.', 'danger')
            return redirect(url_for('profile'))

        
        current_user.username = email  
        current_user.mobile_number = phone

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=current_user)



@app.route('/appointments/<int:appointment_id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=current_user.id).first()

    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    if appointment.status not in ['New', 'Pending']:
        return jsonify({'error': 'Cannot cancel this appointment'}), 400

    appointment.status = 'Cancelled'
    appointment.cancel_reason = 'Cancelled by user'
    db.session.commit()

    return jsonify({'message': 'Appointment cancelled'})


@app.route('/appointments/<int:appointment_id>/cancel_reschedule', methods=['POST'])
@login_required
def cancel_reschedule(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=current_user.id).first()

    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    if appointment.status != 'Rescheduled':
        return jsonify({'error': 'Only rescheduled appointments can be cancelled'}), 400

    appointment.status = 'Cancelled'
    appointment.cancel_reason = 'Cancelled by user (reschedule)'
    db.session.commit()

    return jsonify({'message': 'Rescheduled appointment cancelled'})


@app.route('/appointments/<int:appointment_id>/accept_reschedule', methods=['POST'])
@login_required
def accept_reschedule(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=current_user.id).first()

    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    if appointment.status != 'Rescheduled':
        return jsonify({'error': 'Only rescheduled appointments can be accepted'}), 400

    if not appointment.reschedule_time:
        return jsonify({'error': 'Reschedule time is not set'}), 400

    appointment.status = 'Pending_Rescheduled'
    db.session.commit()

    return jsonify({'message': 'Rescheduled appointment accepted and moved to pending'})


@app.route('/download_bill/<int:appointment_id>')
@login_required
def download_bill(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.user_id != current_user.id or appointment.status != 'Completed' or not appointment.payment_status:
        return "Bill not available.", 403

    html = render_template('bill.html', appointment=appointment)
    pdf_buffer = BytesIO()
    pisa.CreatePDF(html, dest=pdf_buffer)

    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=bill_{appointment.id}.pdf'
    return response

if __name__ == '__main__':
    app.run()
