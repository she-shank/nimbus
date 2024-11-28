
import os
from datetime import datetime
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.conf import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Define the options for the dropdowns
job_titles_options = ["CEO", "CIO", "IT Manager", "Marketing Director", "Sales Lead"]
industries_options = ["Cybersecurity", "Finance", "Healthcare", "Education", "Technology"]
locations_options = ["Europe", "North America", "South America", "Asia", "Africa"]

# OAuth 2.0 configuration
SCOPES = settings.GOOGLE_OAUTH_SETTINGS['scopes']
CLIENT_SECRETS_FILE = settings.GOOGLE_OAUTH_SETTINGS['client_secrets_file']
FOLDER_ID = settings.GOOGLE_OAUTH_SETTINGS['folder_id']

def get_google_flow(request):
    """Initialize and return OAuth 2.0 Flow"""

    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=request.build_absolute_uri('/oauth2callback/')
    )

def initialize_drive_service(credentials):
    """Initialize and return Google Drive service"""
    return build('drive', 'v3', credentials=credentials)

def get_or_create_folder(service, folder_name='campaign_data'):
    """Get or create a folder in Google Drive"""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = results.get('files', [])
    
    if folders:
        return folders[0]['id']
    
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    folder = service.files().create(
        body=folder_metadata,
        fields='id'
    ).execute()
    
    return folder['id']

    """Upload a file to Google Drive using in-memory file object"""
    try:
        folder_id = get_or_create_folder(service)
        
        # Create MediaIoBaseUpload object from in-memory file
        media = MediaIoBaseUpload(
            file_content,
            mimetype=mime_type,
            resumable=True
        )
        
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"File uploaded successfully! File ID: {file['id']}")
        return file['id']
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def oauth2callback(request):
    """Handle OAuth 2.0 callback"""
    flow = get_google_flow(request)
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials
    
    # Store credentials in session
    request.session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    return redirect('questionnaire_form')

def questionnaire_form(request):
    """Handle the main questionnaire form"""
    # Check if user is authenticated with Google
    if 'credentials' not in request.session:
        return
        flow = get_google_flow(request)
        authorization_url, _ = flow.authorization_url(prompt='consent')
        return redirect(authorization_url)

    if request.method == "POST":
        credentials = Credentials(**request.session['credentials'])
        service = initialize_drive_service(credentials)

        # Extract submitted data
        form_data = {
            "objective": request.POST.get("objective"),
            "job_titles": request.POST.get("job_titles"),
            "industries": request.POST.get("industries"),
            "locations": request.POST.get("locations"),
            "engagement": request.POST.get("engagement"),
            "post_date": request.POST.get("post_date"),
            "post_time": request.POST.get("post_time"),
            "followers": request.POST.get("followers"),
            "format": request.POST.get("format"),
            "num_hashtags": request.POST.get("num_hashtags"),
            "hashtag_type": request.POST.get("hashtag_type"),
            "image": request.FILES.get("image"),
            "caption": request.POST.get("caption"),
            "hashtags": request.POST.get("hashtags")
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Handle image upload
        if form_data['image'] and form_data['image'].name.lower().endswith('.jpeg'):
            # Create in-memory buffer for image
            image_buffer = BytesIO(form_data['image'].read())
            image_filename = f"image_{timestamp}.jpeg"
            upload_file_to_drive(
                service,
                image_buffer,
                image_filename,
                'image/jpeg'
            )
        else:
            return HttpResponse("Only JPEG images are allowed.")

        # Create and upload CSV data
        csv_content = StringIO()
        csv_content.write(
            "objective,job_titles,industries,locations,engagement,post_date,post_time,"
            "num_followers,campaign_format,num_hashtags,hashtag_category\n"
            f"{form_data['objective']},{form_data['job_titles']},{form_data['industries']},"
            f"{form_data['locations']},{form_data['engagement']},{form_data['post_date']},"
            f"{form_data['post_time']},{form_data['followers']},{form_data['format']},"
            f"{form_data['num_hashtags']},{form_data['hashtag_type']}"
        )
        csv_buffer = BytesIO(csv_content.getvalue().encode())
        upload_file_to_drive(
            service,
            csv_buffer,
            f"questionaire_{timestamp}.csv",
            'text/csv'
        )

        # Create and upload caption file
        caption_buffer = BytesIO(form_data['caption'].encode())
        upload_file_to_drive(
            service,
            caption_buffer,
            f"caption_{timestamp}.txt",
            'text/plain'
        )

        # Create and upload hashtags file
        hashtags_buffer = BytesIO(form_data['hashtags'].encode())
        upload_file_to_drive(
            service,
            hashtags_buffer,
            f"hashtags_{timestamp}.txt",
            'text/plain'
        )

        return HttpResponse("Form submitted and files uploaded successfully!")

    # Generate form HTML
    csrf_token = get_token(request)
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Campaign Questionnaire</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
            }}
            input[type="text"], input[type="number"], input[type="date"], 
            input[type="time"], select, textarea {{
                width: 100%;
                padding: 8px;
                margin-bottom: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }}
            button {{
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }}
            button:hover {{
                background-color: #45a049;
            }}
        </style>
    </head>
    <body>
        <h1>Campaign Questionnaire</h1>
        <form method="POST" enctype="multipart/form-data">
            <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
            
            <div class="form-group">
                <h3>Upload Image</h3>
                <input type="file" name="image" accept="image/jpeg">
            </div>

            <div class="form-group">
                <h3>Caption and Hashtags</h3>
                <textarea name="caption" rows="4" cols="50" placeholder="Enter your caption here..."></textarea>
                <textarea name="hashtags" rows="4" cols="50" placeholder="Enter hashtags here..."></textarea>
            </div>

            <div class="form-group">
                <h3>Campaign Details</h3>
                <label>Campaign Objective:</label>
                <div>
                    <input type="radio" name="objective" value="brand_awareness" id="brand_awareness">
                    <label for="brand_awareness">Brand Awareness</label>
                </div>
                <div>
                    <input type="radio" name="objective" value="lead_generation" id="lead_generation">
                    <label for="lead_generation">Lead Generation</label>
                </div>
                <div>
                    <input type="radio" name="objective" value="product_promotion" id="product_promotion">
                    <label for="product_promotion">Product Promotion</label>
                </div>
                <div>
                    <input type="radio" name="objective" value="event_promotion" id="event_promotion">
                    <label for="event_promotion">Event Promotion</label>
                </div>
            </div>

            <div class="form-group">
                <label>Target Audience:</label>
                <select name="job_titles">
                    <option value="">Select Job Title</option>
                    {"".join([f'<option value="{title}">{title}</option>' for title in job_titles_options])}
                </select>
                
                <select name="industries">
                    <option value="">Select Industry</option>
                    {"".join([f'<option value="{industry}">{industry}</option>' for industry in industries_options])}
                </select>
                
                <select name="locations">
                    <option value="">Select Location</option>
                    {"".join([f'<option value="{location}">{location}</option>' for location in locations_options])}
                </select>
            </div>

            <div class="form-group">
                <label>Expected Engagement:</label>
                <div>
                    <input type="radio" name="engagement" value="high" id="high">
                    <label for="high">High</label>
                </div>
                <div>
                    <input type="radio" name="engagement" value="medium" id="medium">
                    <label for="medium">Medium</label>
                </div>
                <div>
                    <input type="radio" name="engagement" value="low" id="low">
                    <label for="low">Low</label>
                </div>
            </div>

            <div class="form-group">
                <label>Posting Schedule:</label>
                <input type="date" name="post_date">
                <input type="time" name="post_time">
            </div>

            <div class="form-group">
                <label>Number of Followers:</label>
                <input type="number" name="followers">
            </div>

            <div class="form-group">
                <label>Campaign Format:</label>
                <select name="format">
                    <option value="single_image">Single Image</option>
                    <option value="video">Video</option>
                    <option value="carousel">Carousel</option>
                    <option value="poll">Poll</option>
                    <option value="event">Event</option>
                </select>
            </div>

            <div class="form-group">
                <label>Hashtags:</label>
                <input type="number" name="num_hashtags" placeholder="Number of hashtags">
                <select name="hashtag_type">
                    <option value="niche">Niche</option>
                    <option value="broad">Broad</option>
                </select>
            </div>

            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """
    
    return HttpResponse(html_content)