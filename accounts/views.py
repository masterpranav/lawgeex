from __future__ import unicode_literals
from django.contrib.auth.models import Group
from django.db.models.query import QuerySet

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django import get_version
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured
from django.utils.six import text_type
from model_utils import Choices
from jsonfield.fields import JSONField


try:
    import Image
except ImportError:
    from PIL import Image
from django.shortcuts import render,redirect,get_object_or_404
from accounts.forms import (
	RegistrationForm,
	EditProfileForm,
	DocumentForm,
)
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserChangeForm,PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
import textract, re, StringIO, curses.ascii, pytesseract, glob, os, codecs,sys, subprocess, docx
from django.http import HttpResponse
from accounts.models import Document, Clauses, UserProfile
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models.signals import post_save
from notifications.signals import notify
from notifications.models import Notification,NotificationQuerySet
from datetime import datetime

# Create your views here.
def notify_handler(verb, **kwargs):
    """
    Handler function to create Notification instance upon action signal call.
    """

    # Pull the options out of kwargs
    kwargs.pop('signal', None)
    recipient = kwargs.pop('recipient')
    actor = kwargs.pop('sender')
    optional_objs = [
        (kwargs.pop(opt, None), opt)
        for opt in ('target', 'action_object')
    ]
    public = bool(kwargs.pop('public', True))
    description = kwargs.pop('description', None)
    timestamp = kwargs.pop('timestamp',datetime.now())
    level = kwargs.pop('level', Notification.LEVELS.info)

    # Check if User or Group
    if isinstance(recipient, Group):
        recipients = recipient.user_set.all()
    elif isinstance(recipient, QuerySet) or isinstance(recipient, list):
        recipients = recipient
    else:
        recipients = [recipient]

    new_notifications = []

    for recipient in recipients:
        newnotify = Notification(
            recipient=recipient,
            actor_content_type=ContentType.objects.get_for_model(actor),
            actor_object_id=actor.pk,
            verb=text_type(verb),
            public=public,
            description=description,
            timestamp=timestamp,
            level=level,
        )

        # Set optional objects
        for obj, opt in optional_objs:
            if obj is not None:
                setattr(newnotify, '%s_object_id' % opt, obj.pk)
                setattr(newnotify, '%s_content_type' % opt,
                        ContentType.objects.get_for_model(obj))

        if len(kwargs) and EXTRA_DATA:
            newnotify.data = kwargs

        newnotify.save()
        new_notifications.append(newnotify)

    return new_notifications


# connect the signal
notify.connect(notify_handler, dispatch_uid='notifications.models.notification')

@login_required
def home(request):
	form = DocumentForm(request.POST or None, request.FILES or None)
	if form.is_valid():
		instance = form.save(commit=False)
		a = User.objects.filter(id=2)
		print "***************************************"
		job = UserProfile.objects.get(user=request.user)
		print "job user",job.user
		instance.user = job
		instance.doc_type = instance.doc.url.split(".")[-1]
		instance.save()
		# a=UserProfile.objects.get(user=2)
		arg={
			"recipient":a,
			"sender":request.user,
		}
		
		#notify_handler("has uploaded a document",arg)
		notify.connect(notify_handler, dispatch_uid='notifications.models.notification')
		notify.send(request.user,recipient=a,verb="have uploaded")
		#post_save.connect (sender=Notification)
		#print "Signal executed"
		if instance.doc.url.endswith(".pdf"):
			text = pdf_extractor(instance.doc.url)
			extractor(instance, text)
		elif instance.doc.url.endswith(".jpg"):
			text = pytesseract.image_to_string(Image.open(instance.doc.url))
			extractor(instance, text)
		elif instance.doc.url.endswith(".docx"):
			document_extractor(instance, instance.doc.url)
		elif instance.doc.url.endswith(".doc"):
			document_extractor(instance, instance.doc.url)
	context = {
			"form":form,
		}

	return render(request,'accounts/home.html',context)

def register(request):
	form=RegistrationForm(request.POST or None)
	if form.is_valid():
		instance = form.save(commit=False)
		instance.save()
		return redirect('/account')
	args={'form':form}
	return render(request,'accounts/reg_form.html',args)

@login_required
def view_profile(request):
	args={'user': request.user}
	return render(request, 'accounts/profile.html', args)

@login_required
def edit_profile(request):
	if request.method=='POST':
		form = EditProfileForm(request.POST, instance=request.user)

		if form.is_valid():
			form.save()
			return redirect('/account/profile')

	else:
		form = EditProfileForm(instance=request.user)
		args = {'form': form}
		return render(request,'accounts/edit_profile.html', args)

@login_required
def change_password(request):
	if request.method=='POST':
		form = PasswordChangeForm(data=request.POST, user=request.user)

		if form.is_valid():
			form.save()
			update_session_auth_hash(request, form.user)
			return redirect('/account/profile')
		else:
			return redirect('/account/profile/change-password')
	else:
		form = PasswordChangeForm(user=request.user)
		args = {'form': form}
		return render(request,'accounts/change_password.html', args)

def pdf_extractor(url):
	text = textract.process(url)
	try:
		pdf = codecs.open(url, encoding="ISO8859-1", mode="rb").read()
		startmark = "\xff\xd8"
		startfix = 0
		endmark = "\xff\xd9"
		endfix = 2
		i = 0
		njpg = 0
		while True:
		    istream = pdf.find("stream", i)
		    if istream < 0:
		        break
		    istart = pdf.find(startmark, istream, istream+20)
		    if istart < 0:
		        i = istream+20
		        continue
		    iend = pdf.find("endstream", istart)
		    if iend < 0:
		        raise Exception("Didn't find end of stream!")
		    iend = pdf.find(endmark, iend-20)
		    if iend < 0:
		        raise Exception("Didn't find end of JPG!")
		    istart += startfix
		    iend += endfix
		    # print "JPG %d from %d to %d" % (njpg, istart, iend)
		    jpg = pdf[istart:iend]
		    f_name = re.findall(r"[\w']+", url)[-2]
		    jpgfile = codecs.open(settings.PDF2IMG_URL+f_name+"jpg%d.jpg" % njpg, encoding="ISO8859-1", mode="w")
		    jpgfile.write(jpg)
		    jpgfile.close()
		    njpg += 1
		    i = iend
		for file in sorted(os.listdir(settings.PDF2IMG_URL)):
		    # print file
		    if file.startswith(f_name):
		        # print "yes "+file
		        text = text + pytesseract.image_to_string(Image.open(settings.PDF2IMG_URL+file))
	except:
		pass
	return text

def extractor(instance, text):
    try:
        reload(sys)
        sys.setdefaultencoding('utf8')
        buf = StringIO.StringIO(text)
        flag, conti, r, break_f, content, str_arr, all_val, head_test, head_check = True, 0, False, False, "", [], [], 0, 0
        while flag:
        	if break_f == False:
        		content = buf.readline()
        	if content:
        		content = content.strip()
        		if content:
        			if re.match(r'\d{1,}[.]', content):
        				st = re.search(r'\d{1,}[.]', content).start()
        				ed =re.search(r'\d{1,}[.]', content).end()
        				head_check = int(content[st:(ed-1)])
        				content = content.encode('ascii','ignore')
        				content = re.sub(r'\d{1,}[.]', '', content.decode('utf-8'))
        				content = re.sub(r'\n{1,}', '', content.encode('ascii','ignore')).lstrip()
        				if content == "":
        					title_r=0
        					while content == "":
        						content = buf.readline()
        						content = re.sub(r'\d{1,}[.]', '', content.decode('utf-8'))
        						content = re.sub(r'\n{1,}', '', content.encode('ascii','ignore').decode('utf-8')).lstrip()
        				if '.' in content.decode('utf-8') or ':' in content.decode('utf-8') or ';' in content.decode('utf-8'):
        					if ':' in content.decode('utf-8'):
        						ind = content.index(':')
        						title_r= 1
        					elif '.' in content.decode('utf-8'):
        						ind = content.index('.')
        					else:
        						ind = content.index(';')
        					if ind < 40 or title_r:
        						if len(str_arr):
        							desc = " ".join(str_arr)
        							del str_arr[:]
        							all_val.append(desc)
        						all_val.append(content[0:ind+1])
        						str_arr.append(content[ind+1:])
        						r = True
        					else:
        						if not content.isdigit():
        							str_arr.append(content.strip())
        				else:
        					if len(str_arr):
        						desc = " ".join(str_arr)
        						del str_arr[:]
        						all_val.append(desc)
        					all_val.append(content.strip())
        					head_test=1
        					r = True
        			if r:
        				content = buf.readline()
        				prev_cont, count = ",",0
        				while not re.match(r'\d{1,}[.]', re.sub(r'\n{1,}', '', content.encode('ascii','ignore')).lstrip()) or head_test:
        					if re.match(r'\d{1,}[.]', content):
        						st = re.search(r'\d{1,}[.]', content).start()
        						ed =re.search(r'\d{1,}[.]', content).end()
        						if head_check < int(content[st:(ed-1)]):
        							head_test=0
        							break
        					if content:
        						count = 0
        						content = re.sub(r'\n{1,}', '', content.encode('ascii','ignore')).lstrip()
        						if content.rstrip():
        							if prev_cont[-1] != '.':
        								if not content.isdigit():
        									if "DATED" in content:
        										flag = False
        										break
        									str_arr.append(content.strip())
        							elif content[0].islower() or count < 2:
        								if not content.isdigit():
        									if "DATED" in content:
        										flag = False
        										break
        									str_arr.append(content.strip())
        							else:
        								break
        							r = False
        						else:
        							count = count +1
        						if re.sub(r'\n{1,}', '', content.encode('ascii','ignore')).rstrip():
        							prev_cont = re.sub(r'\n{1,}', '', content.encode('ascii','ignore')).rstrip()
        						content = buf.readline()
        						break_f = True
        					else:
        						flag = False
        						break
        		else:
        			break_f = False
        			continue
        	else:
        		flag = False
        val_prev, index_to_check=",", 0
        for val_check in str_arr:
        	if val_check:
        		if val_check[0].isupper() and val_prev.endswith("."):
        			break
        		val_prev = val_check
        		index_to_check = index_to_check + 1
        all_val.append(" ".join(str_arr[:index_to_check]))
        new_l = len(all_val)-1
        i=0
        while i < new_l:
        	new = Clauses.objects.create(title=all_val[i], clause=all_val[i+1])
        	new.save()
        	instance.clauses.add(new)
        	i=i+2
    except:
    	print "Some Error Occured."
    return None

def document_extractor(instance, url):
	doc = docx.Document(url)
	length = len(doc.paragraphs)
	clause, str_arr, all_val, set_var = False, [], [], 2
	for i in range(length):
		if doc.paragraphs[i]:
			if clause and 'witness' not in doc.paragraphs[i].runs[0].text.lower() and 'dated' not in doc.paragraphs[i].runs[0].text.lower():
				if doc.paragraphs[i].runs[0].font.underline and set_var==1:
					if len(str_arr):
						desc = " ".join(str_arr)
						del str_arr[:]
						all_val.append(desc)
					all_val.append(doc.paragraphs[i].runs[0].text)
					j = 1
					while j:
						try:
							str_arr.append(doc.paragraphs[i].rows[j].text)
							j = j + 1
						except:
							break
				elif doc.paragraphs[i].runs[0].font.bold and set_var==2:
					if len(str_arr):
						desc = " ".join(str_arr)
						del str_arr[:]
						all_val.append(desc)
					all_val.append(doc.paragraphs[i].runs[0].text)
					j = 1
					while j:
						try:
							str_arr.append(doc.paragraphs[i].rows[j].text)
							j = j + 1
						except:
							break
				else:
					str_arr.append(doc.paragraphs[i].text)
			elif 'witness' in doc.paragraphs[i].text.lower() or 'dated' in doc.paragraphs[i].text.lower():
				if clause:
					if len(str_arr):
						desc = " ".join(str_arr)
						del str_arr[:]
						all_val.append(desc)
					break
				else:
					if doc.paragraphs[i].runs[0].font.underline:
						set_var = 1
					else:
						set_var=2
					clause = True
			elif doc.paragraphs[i].paragraph_format.alignment != 1:
				if clause:
					if len(str_arr):
						desc = " ".join(str_arr)
						del str_arr[:]
						all_val.append(desc)
					break
				elif doc.paragraphs[i].runs[0].font.underline:
					set_var = 1
					all_val.append(doc.paragraphs[i].runs[0].text)
					j = 1
					while j:
						try:
							str_arr.append(doc.paragraphs[i].rows[j].text)
							j = j + 1
						except:
							break
					clause = True
	new_l = len(all_val)-1
	i=0
	while i < new_l:
		new = Clauses.objects.create(title=all_val[i], clause=all_val[i+1])
		new.save()
		instance.clauses.add(new)
		i=i+2
	return None
