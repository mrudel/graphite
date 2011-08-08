import re
import errno
from os.path import getmtime
from ConfigParser import ConfigParser
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.conf import settings
from graphite.util import json
from graphite.dashboard.models import Dashboard


fieldRegex = re.compile(r'<([^>]+)>')
defaultScheme = {
  'name' : 'Everything',
  'pattern' : '<category>',
  'fields' : [ dict(name='category', label='Category') ],
}
defaultUIConfig = {
  'default_graph_width'  : 400,
  'default_graph_height' : 250,
  'refresh_interval'     :  60,
  'autocomplete_delay'   : 375,
  'merge_hover_delay'    : 700,
}


class DashboardConfig:
  def __init__(self):
    self.last_read = 0
    self.schemes = [defaultScheme]
    self.ui_config = defaultUIConfig.copy()

  def check(self):
    if getmtime(settings.DASHBOARD_CONF) > self.last_read:
      self.load()

  def load(self):
    schemes = [defaultScheme]
    parser = ConfigParser()
    parser.read(settings.DASHBOARD_CONF)

    for option, default_value in defaultUIConfig.items():
      if parser.has_option('ui', option):
        self.ui_config[option] = parser.getint('ui', option)
      else:
        self.ui_config[option] = default_value

    if parser.has_option('ui', 'automatic_variants'):
      self.ui_config['automatic_variants']   = parser.getboolean('ui', 'automatic_variants')
    else:
      self.ui_config['automatic_variants'] = True

    for section in parser.sections():
      if section == 'ui':
        continue

      scheme = parser.get(section, 'scheme')
      fields = []

      for match in fieldRegex.finditer(scheme):
        field = match.group(1)
        if parser.has_option(section, '%s.label' % field):
          label = parser.get(section, '%s.label' % field)
        else:
          label = field

        fields.append({
          'name' : field,
          'label' : label
        })

      schemes.append({
        'name' : section,
        'pattern' : scheme,
        'fields' : fields,
      })

    self.schemes = schemes


config = DashboardConfig()


def dashboard(request, name=None):
  dashboard_conf_missing = False

  try:
    config.check()
  except OSError, e:
    if e.errno == errno.ENOENT:
      dashboard_conf_missing = True
    else:
      raise

  debug = request.GET.get('debug', False)
  context = {
    'schemes_json' : json.dumps(config.schemes),
    'ui_config_json' : json.dumps(config.ui_config),
    'jsdebug' : debug or settings.JAVASCRIPT_DEBUG,
    'debug' : debug,
    'querystring' : json.dumps( dict( request.GET.items() ) ),
    'dashboard_conf_missing' : dashboard_conf_missing,
  }

  if name is not None:
    try:
      dashboard = Dashboard.objects.get(name=name)
    except Dashboard.DoesNotExist:
      context['initialError'] = "Dashboard '%s' does not exist." % name
    else:
      context['initialState'] = dashboard.state

  return render_to_response("dashboard.html", context)


def save(request, name):
  # Deserialize and reserialize as a validation step
  state = str( json.dumps( json.loads( request.POST['state'] ) ) )

  try:
    dashboard = Dashboard.objects.get(name=name)
  except Dashboard.DoesNotExist:
    dashboard = Dashboard.objects.create(name=name, state=state)
  else:
    dashboard.state = state
    dashboard.save();

  return json_response( dict(success=True) )


def load(request, name):
  try:
    dashboard = Dashboard.objects.get(name=name)
  except Dashboard.DoesNotExist:
    return json_response( dict(error="Dashboard '%s' does not exist. " % name) )

  return json_response( dict(state=json.loads(dashboard.state)) )


def delete(request, name):
  try:
    dashboard = Dashboard.objects.get(name=name)
  except Dashboard.DoesNotExist:
    return json_response( dict(error="Dashboard '%s' does not exist. " % name) )
  else:
    dashboard.delete()
    return json_response( dict(success=True) )


def find(request):
  query = request.REQUEST['query']
  query_terms = set( query.lower().split() )
  results = []

  # Find all dashboard names that contain each of our query terms as a substring
  for dashboard in Dashboard.objects.all():
    name = dashboard.name.lower()
    if name.startswith('temporary-'):
      continue

    found = True # blank queries return everything
    for term in query_terms:
      if term in name:
        found = True
      else:
        found = False
        break

    if found:
      results.append( dict(name=dashboard.name) )

  return json_response( dict(dashboards=results) )


def help(request):
  context = {}
  return render_to_response("dashboardHelp.html", context)


def create_temporary(request):
  state = str( json.dumps( json.loads( request.POST['state'] ) ) )
  i = 0
  while True:
    name = "temporary-%d" % i
    try:
      Dashboard.objects.get(name=name)
    except Dashboard.DoesNotExist:
      dashboard = Dashboard.objects.create(name=name, state=state)
      break
    else:
      i += 1

  return json_response( dict(name=dashboard.name) )


def json_response(obj):
  return HttpResponse(mimetype='text/json', content=json.dumps(obj))
