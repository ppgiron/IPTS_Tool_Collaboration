# GitHub_Username_Websearch.py - Flask web application for GitHub User Search (Codespace-friendly)
import os
import requests
import pandas as pd
from datetime import datetime
import logging
import time
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_bootstrap import Bootstrap


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='github_search.log'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))  # for flash messages
bootstrap = Bootstrap(app)

# Configuration
RESULTS_FILE = 'github_search_results.xlsx'

def search_github(search_type, query, token=None):
    """
    Generic function to search GitHub users by different criteria.
    
    Args:
        search_type (str): Type of search ('email' or 'name')
        query (str): Search query
        token (str, optional): GitHub API token
        
    Returns:
        list: List of dictionaries containing user information
    """
    if not query:
        logger.warning(f"Empty {search_type} provided")
        return []
        
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    
    params = {'q': f'{query} in:{search_type}'}
    
    try:
        response = requests.get(
            'https://api.github.com/search/users',
            headers=headers,
            params=params,
            timeout=10
        )
        
        # Handle rate limiting
        if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
            if int(response.headers['X-RateLimit-Remaining']) == 0:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                wait_time = max(0, reset_time - int(time.time()))
                logger.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds")
                return [], f"GitHub API rate limit exceeded. Try again in {wait_time} seconds or use a token."
        
        response.raise_for_status()
        results = response.json()
        
        # Log search metadata
        result_count = len(results.get('items', []))
        logger.info(f"{search_type.capitalize()} search for '{query}' found {result_count} results")
        
        # Get more detailed user info
        users = []
        for user in results.get('items', []):
            user_data = {
                'login': user['login'],
                'url': user['html_url'],
                'avatar_url': user['avatar_url'],
                'type': user['type']
            }
            users.append(user_data)
            
        return users, None
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error searching by {search_type}: {str(e)}"
        logger.error(error_msg)
        return [], error_msg
    except Exception as e:
        error_msg = f"Error searching by {search_type}: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

def save_to_excel(search_type, input_data, results):
    """Save search results to Excel file with error handling"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create DataFrame with new entry
    usernames = [user['login'] for user in results]
    new_entry = pd.DataFrame({
        'Timestamp': [timestamp],
        'Search Type': [search_type],
        'Input': [input_data],
        'Results': [', '.join(usernames) if usernames else 'No results'],
        'Result Count': [len(results)]
    })
    
    try:
        # Try to read existing file
        if os.path.exists(RESULTS_FILE):
            df = pd.read_excel(RESULTS_FILE)
            updated_df = pd.concat([df, new_entry], ignore_index=True)
        else:
            # Create new file if it doesn't exist
            updated_df = new_entry
        
        # Save to Excel
        updated_df.to_excel(RESULTS_FILE, index=False)
        logger.info(f"Results saved to '{RESULTS_FILE}'")
        return True
    except Exception as e:
        logger.error(f"Error saving to Excel: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    search_type = request.form.get('search_type')
    query = request.form.get('query', '').strip()
    token = request.form.get('token', '').strip() or None
    
    if not query:
        flash('Please enter a search query', 'warning')
        return redirect(url_for('index'))
    
    users, error = search_github(search_type, query, token)
    
    if error:
        flash(error, 'danger')
        return render_template('index.html', search_type=search_type, query=query)
    
    # Save results to Excel
    save_to_excel(search_type, query, users)
    
    return render_template('results.html', 
                          users=users, 
                          search_type=search_type, 
                          query=query, 
                          count=len(users))

@app.route('/download')
def download():
    if os.path.exists(RESULTS_FILE):
        return send_file(RESULTS_FILE, as_attachment=True)
    else:
        flash('No search results file exists yet', 'warning')
        return redirect(url_for('index'))

@app.route('/history')
def history():
    if os.path.exists(RESULTS_FILE):
        try:
            df = pd.read_excel(RESULTS_FILE)
            searches = df.to_dict('records')
            return render_template('history.html', searches=searches)
        except Exception as e:
            logger.error(f"Error reading history: {str(e)}")
            flash('Error reading search history', 'danger')
    else:
        flash('No search history available', 'info')
    
    return redirect(url_for('index'))

# Create necessary files and directories
def create_files():
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create static directory for CSS
    os.makedirs('static', exist_ok=True)
    
    # Write template files
    with open('templates/base.html', 'w') as f:
        f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}GitHub User Search{% endblock %}</title>
    {{ bootstrap.load_css() }}
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">GitHub User Search</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">Search</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('history') }}">History</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('download') }}">Download Results</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>

    <footer class="footer mt-5 py-3 bg-light">
        <div class="container text-center">
            <span class="text-muted">GitHub User Search Tool</span>
        </div>
    </footer>

    {{ bootstrap.load_js() }}
</body>
</html>''')

    with open('templates/index.html', 'w') as f:
        f.write('''{% extends "base.html" %}

{% block title %}GitHub User Search{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h2 class="mb-0">Search GitHub Users</h2>
            </div>
            <div class="card-body">
                <form action="{{ url_for('search') }}" method="post">
                    <div class="mb-3">
                        <label for="search_type" class="form-label">Search Type</label>
                        <select class="form-select" id="search_type" name="search_type" required>
                            <option value="email" {% if search_type == "email" %}selected{% endif %}>Email</option>
                            <option value="name" {% if search_type == "name" %}selected{% endif %}>Full Name</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="query" class="form-label">Search Query</label>
                        <input type="text" class="form-control" id="query" name="query" 
                               value="{{ query|default('') }}" required placeholder="Enter email address or full name">
                    </div>
                    <div class="mb-3">
                        <label for="token" class="form-label">GitHub API Token (Optional)</label>
                        <input type="password" class="form-control" id="token" name="token" 
                               placeholder="For higher rate limits">
                        <div class="form-text">Leave empty to use without authentication (lower rate limits)</div>
                    </div>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Search</button>
                    </div>
                </form>
            </div>
            <div class="card-footer">
                <div class="text-muted small">
                    <p>This tool searches for GitHub users by email address or full name.</p>
                    <p>All search results are automatically saved and can be viewed in the History tab.</p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}''')

    with open('templates/results.html', 'w') as f:
        f.write('''{% extends "base.html" %}

{% block title %}Search Results{% endblock %}

{% block content %}
<div class="card mb-4">
    <div class="card-header bg-success text-white d-flex justify-content-between align-items-center">
        <h2 class="mb-0">Search Results</h2>
        <a href="{{ url_for('index') }}" class="btn btn-outline-light">New Search</a>
    </div>
    <div class="card-body">
        <div class="alert alert-info">
            Found {{ count }} GitHub users for {{ search_type }} search: <strong>{{ query }}</strong>
        </div>
        
        {% if users %}
            <div class="row row-cols-1 row-cols-md-3 g-4">
                {% for user in users %}
                    <div class="col">
                        <div class="card h-100">
                            <img src="{{ user.avatar_url }}" class="card-img-top p-3" alt="{{ user.login }}'s avatar">
                            <div class="card-body">
                                <h5 class="card-title">{{ user.login }}</h5>
                                <p class="card-text">Type: {{ user.type }}</p>
                                <a href="{{ user.url }}" target="_blank" class="btn btn-primary">View Profile</a>
                            </div>
                        </div>
                    </div>
                {% endfor %}
            </div>
        {% else %}
            <div class="alert alert-warning">
                No users found matching your search criteria.
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}''')

    with open('templates/history.html', 'w') as f:
        f.write('''{% extends "base.html" %}

{% block title %}Search History{% endblock %}

{% block content %}
<div class="card">
    <div class="card-header bg-info text-white d-flex justify-content-between align-items-center">
        <h2 class="mb-0">Search History</h2>
        <a href="{{ url_for('download') }}" class="btn btn-outline-light">Download Excel</a>
    </div>
    <div class="card-body">
        {% if searches %}
            <div class="table-responsive">
                <table class="table table-striped table-hover">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Search Type</th>
                            <th>Query</th>
                            <th>Results</th>
                            <th>Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for search in searches %}
                            <tr>
                                <td>{{ search.Timestamp }}</td>
                                <td>{{ search['Search Type'] }}</td>
                                <td>{{ search.Input }}</td>
                                <td>{{ search.Results }}</td>
                                <td>{{ search['Result Count'] }}</td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <div class="alert alert-info">No search history found.</div>
        {% endif %}
    </div>
</div>
{% endblock %}''')

    with open('static/style.css', 'w') as f:
        f.write('''/* Custom styles */
body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

.footer {
    margin-top: auto;
}

/* Card styling */
.card {
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.card-header h2 {
    font-size: 1.5rem;
}
''')
    
    # Create requirements.txt
    with open('requirements.txt', 'w') as f:
        f.write('''flask==2.3.3
flask-bootstrap-components==0.2.0
pandas==2.0.3
openpyxl==3.1.2
requests==2.31.0
gunicorn==21.2.0
''')
    
    # Create README file with Codespace instructions
    with open('README.md', 'w') as f:
        f.write('''# GitHub User Search Web Application

A web-based interface for searching GitHub users by email address or full name.

## Features

- Search GitHub users by email or full name
- View user profiles with avatars
- Track search history
- Download search results as Excel file
- Optional GitHub API token support for higher rate limits

## Running in GitHub Codespaces

1. Open the repository in GitHub Codespaces
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python app.py
   ```
4. The application will be available at the port forwarded URL (typically shown in the terminal or in the Ports tab)

### Port Forwarding

Codespaces should automatically detect and forward port 5000. If not:
1. In VS Code, go to the "PORTS" tab at the bottom
2. Click "Forward a Port" 
3. Enter port 5000
4. Make it public if you want to share access

## Running Locally

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python app.py
   ```
4. Open your browser and go to http://localhost:5000/

## Requirements

- Python 3.7+
- Flask
- Flask-Bootstrap
- Pandas
- Requests
''')

if __name__ == '__main__':
    # Create all necessary files
    create_files()
    
    # Get port from environment variable (for Codespaces compatibility)
    port = int(os.environ.get('PORT', 5000))
    
    # Set host to 0.0.0.0 to make it accessible from outside the container
    print(f"\nStarting GitHub Search app on port {port}")
    print("Access URLs:")
    print(f"- Local: http://localhost:{port}")
    print(f"- Remote: http://0.0.0.0:{port} (In Codespaces, use the forwarded URL)")
    print("\nPress Ctrl+C to stop the server")
    
    # Run the app with settings that work well in Codespaces
    app.run(host='0.0.0.0', port=port, debug=True)
