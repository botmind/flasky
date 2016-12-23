from flask import Flask, render_template, session, redirect, url_for, flash
from datetime import datetime
from threading import Thread

import os

from flask_script import Shell
from flask_script import Manager
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_migrate import Migrate, MigrateCommand
from flask_mail import Mail, Message
from flask_wtf import Form
from wtforms import StringField, SubmitField
from wtforms.validators import Required



basedir = os.path.abspath(os.path.dirname(__file__))
#print (basedir)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pneumatic'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['FLASKY_MAIL_SUBJECT_PREFIX'] = '[Flasky]'
app.config['FLASKY_MAIL_SENDER'] = 'Flasky Admin <flasky@example.com>'
app.config['FLASKY_ADMIN'] = os.environ.get('FLASKY_ADMIN')

db = SQLAlchemy(app)
manager = Manager(app)
bootstrap = Bootstrap(app)
moment = Moment(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)
mail = Mail(app)

def make_shell_context(): #registers app, db, and models so that they are automatically imported into shell
	return dict(app=app, db=db, User=User, Role=Role)

manager.add_command('shell', Shell(make_context=make_shell_context))

def send_async_email(app, msg):
	with app.app_context(): #we have to artificially create the application context, because the mail extension expects it, and when mail.send() executes in a different thread, it does not have the context naturally
		mail.send(msg)

def send_email(to, subject, template, **kwargs):
	msg = Message(app.config['FLASKY_MAIL_SUBJECT_PREFIX'] + subject, sender=app.config['FLASKY_MAIL_SENDER'], recipients=[to])
	msg.body = render_template(template + '.txt', **kwargs)
	msg.html = render_template(template + '.html', **kwargs)
	thr = Thread(target=send_async_email, args=[app, msg])
	thr.start()
	return thr


class NameForm(Form):
	#fields in form defined as class variables
	name = StringField('What is your name?', validators=[Required()])
	submit = SubmitField('Submit')


class Role(db.Model):
	__tablename__ = 'roles'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(64), unique=True)
	users = db.relationship('User', backref='role', lazy='dynamic') #adds a role attribute to User, so that we can acces the Role model as an object rather than a foreign key
	#lazy='dynamic' ensures that a Role.users query is not automatically executed as Role.users.all(), such that we can refine it with additional filters

	def __repr__(self):
		return '<Role %r>' % self.name

class User(db.Model):
	__tablename__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(64), unique=True, index=True)
	role_id = db.Column(db.Integer, db.ForeignKey('roles.id')) #should have id values from the roles table

	def __repr__(self):
		return '<User %r>' % self.username


@app.route('/', methods=['GET', 'POST'])
def index():
	form = NameForm()
	if form.validate_on_submit():
		user = User.query.filter_by(username=form.name.data).first() #check if user already exists in db
		if user is None:
			user = User(username=form.name.data) #if the user does not exist, create him in the db
			db.session.add(user)
			session['known'] = False
			if app.config['FLASKY_ADMIN']:
				send_email(app.config['FLASKY_ADMIN'], 'New User', 'mail/new_user', user=user)
		else:
			session['known'] = True #add a marker in the cookie if the user previously existed or not
		session['name'] = form.name.data #store the name from the form in the local session (cookie)
		form.name.data = ''
		return redirect(url_for('index'))
	return render_template('index.html', current_time=datetime.utcnow(), form=form, name=session.get('name'), known=session.get('known', False)) #if nothing has been saved to the session for name, this will be None; get returns a default value of None for missing key; for 'known' we specify a default return value of Flase if the key is missing

@app.route('/user/<name>')
def user(name):
	return render_template('user.html', name=name)

@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
	return render_template('500.html'), 500

if __name__ == '__main__':
	manager.run()