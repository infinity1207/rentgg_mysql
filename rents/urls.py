from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:

urlpatterns = patterns('rents.views',
        url(r'^$', 'index', name='index'),
        url(r'^customer/(?P<customer_id>\d+)/statement$', 'statement', name='statement'),
        url(r'^customer/(?P<customer_id>\d+)/$', 'customer', name='customer'),
)
