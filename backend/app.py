from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import os
import sqlite3


app = Flask(__name__)

# Configure SQLite database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username

with app.app_context():
    db.create_all()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    new_user = User(username=data['username'], email=data['email'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User created successfully!'}), 201

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    output = []
    for user in users:
        output.append({'id': user.id, 'username': user.username, 'email': user.email})
    return jsonify({'users': output})

@app.route('/table_manager')
def table_manager():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template('table_manager.html', tables=tables)

@app.route('/table_data/<table_name>')
def table_data(table_name):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row # To get dictionary-like rows
    cursor = conn.cursor()

    # Get schema
    cursor.execute(f"PRAGMA table_info({table_name});")
    schema = [dict(row) for row in cursor.fetchall()]

    # Get data (limit to 100 rows for display)
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 100;")
    data = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(schema=schema, data=data)

@app.route('/add_record/<table_name>', methods=['POST'])
def add_record(table_name):
    new_record = request.get_json()
    if not new_record:
        return jsonify({'error': 'No data provided'}), 400

    # Use SQLAlchemy to add record
    try:
        # Assuming all tables have an 'id' column as primary key and other columns match model fields
        # This approach requires a model for each table, or a more dynamic model creation
        # For simplicity, let's assume we are dealing with the 'user' table for now
        if table_name == 'user':
            username = new_record.get('username')
            email = new_record.get('email')
            if not username or not email:
                return jsonify({'error': 'Username and Email are required'}), 400
            
            new_user = User(username=username, email=email)
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Record added successfully!'}), 201
        else:
            return jsonify({'error': f'Table {table_name} not supported for adding records via SQLAlchemy yet.'}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        columns = ', '.join(new_record.keys())
        placeholders = ', '.join(['?' for _ in new_record.values()])
        values = tuple(new_record.values())
        cursor.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
        conn.commit()
        return jsonify({'success': True, 'message': 'Record added successfully!'}), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/delete_record/<table_name>', methods=['DELETE'])
def delete_record(table_name):
    record_id = request.get_json().get('id')
    if not record_id:
        return jsonify({'error': 'No record ID provided'}), 400

    try:
        if table_name == 'user':
            user_to_delete = User.query.get(record_id)
            if user_to_delete:
                db.session.delete(user_to_delete)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Record deleted successfully!'}), 200
            else:
                return jsonify({'error': 'Record not found'}), 404
        else:
            return jsonify({'error': f'Table {table_name} not supported for deleting records via SQLAlchemy yet.'}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/execute_script', methods=['POST'])
def execute_script():
    script = request.json.get('script')
    if not script:
        return jsonify({'error': 'No script provided'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    results = []
    try:
        cursor.executescript(script)
        conn.commit()
        # Attempt to fetch results if it was a SELECT statement
        # This is a simplified approach; a more robust solution would parse the SQL
        if script.strip().lower().startswith('select'):
            # Re-execute the select statement to fetch results after commit
            # This might not work for all multi-statement scripts
            cursor.execute(script)
            results = [dict(row) for row in cursor.fetchall()]
        return jsonify({'success': True, 'results': results})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@app.route('/script_executor')
def script_executor():
    return render_template('script_executor.html')

def get_db_connection():
    conn = sqlite3.connect('database.sqlite')
    conn.row_factory = sqlite3.Row
    return conn

if __name__ == '__main__':
    app.run(debug=True)