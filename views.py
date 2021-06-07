from django.shortcuts import render, redirect
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseRedirect, FileResponse, JsonResponse
from django.urls import reverse
from threading import Thread
from botocore.client import Config
from smart_open import open
import os
import random
import string
import time
import logging
import json
import boto3

from .models import ServiceRecord
from .forms import SplitForm
from . import handler
from .bucketManager import get_presigned_url


# Homepage View
def home(request):
    return render(request, os.path.join('split', 'home.html'))

	
# S3 URL Generator View, called by JavaScript only
def sign_s3(request):
	# Generate a random unique identifying tag for the file
	file_name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
	file_type = request.GET.get('file_type')
  
	# Create .txt that contains URL link and other details
	with open(os.path.join('media', 'urltexts', file_name + '.txt'), 'w', encoding="utf-8") as txtfile:
		toWrite = 'https://%s.s3.us-east-2.amazonaws.com/%s' % (S3_BUCKET, file_name)
		txtfile.write(toWrite + '\n')
		txtfile.write(request.GET.get('file_name'))
  
	# Bucket initialization and presigned post request
	S3_BUCKET = os.environ.get('AWS_STORAGE_BUCKET_NAME')
	REGION = 'us-east-2'

	s3 = boto3.client('s3', region_name=REGION, config=Config(signature_version='s3v4'), 
	aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

	presigned_post = s3.generate_presigned_post(
		Bucket = S3_BUCKET,
		Key = file_name,
		Fields = {"acl": "public-read", "Content-Type": file_type},
		Conditions = [
		{"acl": "public-read"},
		{"Content-Type": file_type}
		],
		ExpiresIn = 3600
	)
	return JsonResponse({
		'data': presigned_post,
		'url': 'https://%s.s3.us-east-2.amazonaws.com/%s' % (S3_BUCKET, file_name),
		'txtName': file_name
	})

	
# Split Tool View
def split(request):
    if request.method == 'POST':
		# Process the form if it is a POST request
        form = SplitForm(request.POST, request.FILES)
        if form.is_valid():
            formData = form.cleaned_data
            audioFile = formData['avfile']
            times = formData['times']
            titles = formData['titles']
            extension = formData['fileType']
            fileName = formData['fileName']
            url = formData['url']
            tag = formData['keyFileInfo']
	    
			# Save data as a service record (object)
            if (request.user.is_authenticated):
                record = ServiceRecord(filename=fileName, filetype=extension, user=request.user, timestamps=formData['timestamps'])
            else:
                record = ServiceRecord(filename=fileName, filetype=extension, timestamps=formData['timestamps'])
            record.save()

			# Starts the splitting process (sample at bottom). Multithreaded so that a redirect response can be immediately sent
            if extension == 'wav':
                Thread(target=handler.trimWAV, args=(url, times, titles, tag)).start()
            else:
                Thread(target=handler.trimMP3, args=(url, times, titles, tag)).start()
            return redirect('download', tag=tag)
    else:
		# Load the form if it is a GET request
        form = SplitForm()
    return render(request, os.path.join('split', 'ss-tool.html'), {'form': form})

	
# Download View
def download(request, tag): 
    # Checks periodically for completed file
    time.sleep(10)
    try:
		# The existence of the .txt file signals the completion of the process
        txtpath = os.path.join("media", "tempzips", 'SS-' + tag + '.txt')
        with open(txtpath, 'rb') as f:
			# Time check ensures that an old file is not retrieved. (This would occur when the user resubmits a request without reloading or reuploading)
            if time.time() - os.path.getmtime(txtpath) > 11:
                return redirect('download', tag=tag)
        return FileResponse(open(os.path.join("media", "tempzips",'SS-' + tag + '.zip'), 'rb'), filename = 'SSArchive.zip')
    # Otherwise redirect
    except:
        return redirect('download', tag=tag)
    

# Loader.to Downloader Tool View
def loaderdl(request):
    return render(request, os.path.join('split', 'loaderdl.html'))

	
# About View
def about(request):
    return render(request, os.path.join('split', 'about.html'))
	