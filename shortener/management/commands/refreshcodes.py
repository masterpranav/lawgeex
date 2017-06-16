from django.core.management.base import BaseCommand,CommandError
from shortener.models import PcURL


class Command(BaseCommand):
	help='Refreshes all PcURL shortcodes'

	def add_arguments(self,parser):
		parser.add_argument('--items',type=int)

	def handle(self,*args,**options):
		return PcURL.objects.refresh_shortcodes(items=options['items'])