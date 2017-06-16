from django.http import HttpResponse,HttpResponseRedirect
from django.shortcuts import render,get_object_or_404
from django.views import View
from shortener.models import PcURL
from .forms import SubmitUrlForm
from analytics.models import ClickEvent

class HomeView(View):
	def get(self,request,*args,**kwargs):
		the_form=SubmitUrlForm()
		context={
			"title":"Url.co",
			"form": the_form
		}
		return render(request,"shortener/home.html",context)

	def post(self,request,*args,**kwargs):
		form=SubmitUrlForm(request.POST)
		context={
				"title":"Url.co",
				"form": form
			}
		template="shortener/home.html"	
		if form.is_valid():
			new_url=form.cleaned_data.get("url")
			obj,created= PcURL.objects.get_or_create(url=new_url)
			context={
				"object":obj,
				"created": created,
			}
			if created:
				template="shortener/success.html"
			else:
				template="shortener/already_exists.html"	
		return render(request,template,context)

class URLRedirectView(View): #Class Based View
	def get(self,request,shortcode=None,*args,**kwargs):
		obj=get_object_or_404(PcURL,shortcode=shortcode)
		print ClickEvent.objects.create_event(obj)
		return HttpResponseRedirect(obj.url)