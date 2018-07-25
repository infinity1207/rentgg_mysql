# -*- coding: utf-8 -*-
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.db.models import Count, Sum
from rents.models import Customer, Rent, Revert, RentDetail, RevertDetail, Product
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.cache import never_cache
from django.utils.translation import ugettext as _
from django.contrib.auth import logout as auth_logout, REDIRECT_FIELD_NAME
from datetime import datetime, timedelta
from django.utils import timezone

def authenticate(func):
    @never_cache
    def _wrapper(request, *args, **kwargs):
        """
        Displays the login form for the given HttpRequest.
        """
        if not request.user.is_authenticated():
            from django.contrib.auth.views import login
            context = {
                'title': _('Log in'),
                'app_path': request.get_full_path(),
                REDIRECT_FIELD_NAME: request.get_full_path(),
            }
            defaults = {
                'extra_context': context,
                #'current_app': self.name,
                #'authentication_form': self.login_form or AdminAuthenticationForm,
                'template_name': 'admin/login.html',
            }
            return login(request, **defaults)
        return func(request, *args, **kwargs)
    return _wrapper


class RentListItem(object):
    def __init__(self, revertObj):
        self.obj = revertObj
        if isinstance(self.obj, Revert):
            self.isRevert = True
        else:
            self.isRevert = False

# return[(租借/归还, 描述, 日期)]
def _fetchRentList(rentObjs, revertObjs):
    rent_list = []
    lastIndex = -1 
    for rentObj in rentObjs:
        for x in range(len(revertObjs)):
            if x <= lastIndex:
                continue
            revertObj = revertObjs[x]
            if revertObj.revert_date >= rentObj.rent_date:
                rent_list.append(RentListItem(revertObj))
                lastIndex = x 
        #end for x....

        rent_list.append(RentListItem(rentObj))
    #end for rentObj...

    for x in range(lastIndex + 1, len(revertObjs)):
        revertObj = revertObjs[x]
        rent_list.append(RentListItem(revertObj))
    #end for x....

    return rent_list

@authenticate
def index(request):
    # context = {
        # 'customer_list':[customer1, customer2,]
        # 'total':{'remain': '', 'receivable':'', 'received':'', 'debt':''},
    # }
    context = {'customer_list':[], 'total':{}}

    totalReceivable = 0
    totalDebt = 0;
    for cust in Customer.objects.all():
        cust.statist()
        totalReceivable += cust.receivableValue
        totalDebt += cust.debtValue
        context['customer_list'].append(cust)

    context['total']['remain'] = Customer.clsRemain() 
    context['total']['received'] = Customer.clsReceived()
    context['total']['receivable'] = totalReceivable
    context['total']['debt'] = totalDebt

    return render(request, "rents/index.html", context)

@authenticate
def customer(request, customer_id):
    customer = get_object_or_404(Customer, pk = customer_id)
    customer.statist()

    rentObjs = customer.rent_set.order_by('-rent_date')
    revertObjs = customer.revert_set.order_by('-revert_date')
    rent_list = _fetchRentList(rentObjs, revertObjs)

    pageIndex = request.GET.get('p')    #start from 1
    paginator = Paginator(rent_list, 100)

    try:
        rent_list = paginator.page(pageIndex)
    except PageNotAnInteger:
        rent_list = paginator.page(1)
    except EmptyPage:
        rent_list = paginator.page(paginator.num_pages)

    return render(request, 
                    "rents/customer.html", 
                    {
                        "customer":customer,
                        "rent_list":rent_list, 
                    })

@authenticate
def statement(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    statement_list = customer.calc_rent_amount_detail() 

    l = ['', 'info']
    d = {}
    i = 0
    for product in Product.objects.all():
        d[product.name] = l[i % len(l)]
        i = i + 1
    for item in statement_list:
        item['class'] = d[item['product']]

    context = {
        'customer': customer,
        'detail': statement_list,
    }
    return render(request, 'rents/statement.html', context)