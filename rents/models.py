# -*- coding: utf-8 -*-
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum
import logging
logger = logging.getLogger('rents.' + __name__)

# import sys 
# reload(sys) 
# sys.setdefaultencoding('utf-8')

# Create your models here.
class Customer(models.Model):
    name = models.CharField(u"客户名称", max_length=200)
    contacter = models.CharField(u"联系人", max_length=50, blank=True)
    tel = models.CharField(u"电话", max_length=50, blank=True)
    address = models.CharField(u"地址", max_length=200, blank=True)
    remarks = models.CharField(u"备注", max_length=500, blank=True)

    def __unicode__(self):
        return self.name

    def statist(self):
        """统计各项汇总信息"""
        self.remainValue = self.remain()
        self.receivableValue = self.receivable()
        self.receivedValue = self.received()
        self.debtValue = self.receivableValue - self.receivedValue
        
    @classmethod
    def clsRemain(cls, **kwarg):
        total = True 
        if kwarg.has_key('customerId'):
            customerId = kwarg['customerId']
            total = False

        if total:
            rentdetail_qs = RentDetail.objects.all()
        else: 
            rentdetail_qs = RentDetail.objects.filter(rent__customer__exact = customerId)
        # 实现了SQL语句的GroupBy的效果
        # select product_id,sum(quantity) from rents_rentdetail Group By product_id
        rentdetail_ls = rentdetail_qs.values('product').annotate(sum = Sum('quantity'))

        if total:
            revertdetail_qs = RevertDetail.objects.all()
        else:
            revertdetail_qs = RevertDetail.objects.filter(revert__customer__exact = customerId)
        revertdetail_ls = revertdetail_qs.values('product').annotate(sum = Sum('quantity'))

        for rentdetail in rentdetail_ls:
            for revertdetail in revertdetail_ls:
                if rentdetail['product'] == revertdetail['product']:
                    rentdetail['sum'] -= revertdetail['sum']

        for rentdetail in rentdetail_ls:
            rentdetail['product_name'] = Product.objects.get(id = rentdetail['product']).name
            rentdetail['unit'] = Product.objects.get(id=rentdetail['product']).unit

        remainStr = ""
        for item in rentdetail_ls:
            remainStr += '[%(product_name)s %(sum)8.2f%(unit)s]' % (item)
        return remainStr 

    def remain(self):
        return Customer.clsRemain(customerId = self.id)
    
    def receivable(self):
        l = self.calc_rent_amount_detail()
        sum = 0
        for item in l:
            sum += item['amount']
        return sum

    def calc_rent_amount_detail(self):
        """
        计算客户的租金结算表
        [
            {
                'date',
                'product',
                'unit',
                'price',
                'out',
                'in',
                'remain',
                'begin_date',
                'end_date',
                'days',
                'amount',
            }
        ]
        """
        l = []
        for product in Product.objects.all():
            l.extend(self._calcProductDetail(self, product))

        return l

    def _keep2Decimal(self, f_value):
        return float("%.2f" % (f_value))

    def _calcProductDetail(self, customer, product):
        all_list = []
        rent_detail_list = list(RentDetail.objects.filter(rent__customer_id=customer.id, product__id=product.id).values('rent__rent_date', 'product').annotate(Sum('quantity')).order_by('rent__rent_date'))
        revert_detail_list = list(RevertDetail.objects.filter(revert__customer_id=customer.id, product__id=product.id).values('revert__revert_date', 'product').annotate(Sum('quantity')).order_by('revert__revert_date'))
        all_list = rent_detail_list[:]
        for item_revert in revert_detail_list:
            for i in range(len(all_list) - 1, -1, -1):
                if 'rent__rent_date' in all_list[i]:
                    if item_revert['revert__revert_date'] >= all_list[i]['rent__rent_date']:
                        all_list.insert(i+1, item_revert)
                        break
                else:
                    if item_revert['revert__revert_date'] >= all_list[i]['revert__revert_date']:
                        all_list.insert(i+1, item_revert)
                        break

        l = []
        for item in all_list:
            if 'rent__rent_date' in item:
                remain = 0
                if len(l) > 0:
                    last = l[-1]
                    last['end_date'] = item['rent__rent_date'] - timedelta(1)
                    last['days'] = (last['end_date'] - last['date']).days + 1
                    last['amount'] = self._keep2Decimal(last['days'] * last['remain'] * last['price'])
                    remain = last['remain']

                d = {}
                d['date'] = item['rent__rent_date']
                d['product'] = product.name
                d['unit'] = product.unit
                d['price'] = product.unit_price
                d['out'] = item['quantity__sum']
                d['in'] = None
                d['remain'] = remain + item['quantity__sum']
                d['begin_date'] = d['date']
                d['end_date'] = timezone.now().date()
                d['days'] = (d['end_date'] - d['date']).days + 1
                d['amount'] = self._keep2Decimal(d['days'] * d['remain'] * d['price'])
                l.append(d)
            else:
                remain = 0
                if len(l) > 0:
                    last = l[-1]
                    last['end_date'] = item['revert__revert_date']
                    last['days'] = (last['end_date'] - last['date']).days + 1
                    last['amount'] = self._keep2Decimal(last['days'] * last['remain'] * last['price'])
                    remain = last['remain']
                else:
                    continue

                d = {}
                d['date'] = item['revert__revert_date']
                d['product'] = product.name
                d['unit'] = product.unit
                d['price'] = product.unit_price
                d['out'] = None
                d['in'] = item['quantity__sum']
                d['remain'] = max(remain - item['quantity__sum'], 0)
                d['begin_date'] = d['date'] + timedelta(1)
                d['end_date'] = timezone.now().date()
                d['days'] = (d['end_date'] - d['date']).days + 1
                d['amount'] = self._keep2Decimal(d['days'] * d['remain'] * d['price'])
                l.append(d)

        return l

    # 应收
    def receivable_old(self):
        # 得到首笔租借的日期
        # 从首笔租借日期开始循环到今天，计算每一天的产品租借累积数量
        # 根据每一天的累积租借数量计算当天的应收并计入总应收
        rentDetailQS = RentDetail.objects.filter(rent__customer=self.id).order_by('rent__rent_date')
        revertDetailQS = RevertDetail.objects.filter(revert__customer=self.id).order_by('revert__revert_date')

        # 存储每天参与应收计算的产品数量
        # dayQuantitys = {
            # '2014-01-01': {product:10, product:10,},
            # '2014-01-02': {product:10, product:10,},
        # }
        dayQuantitys = {}
        lastDayDetail = None
        for detail in rentDetailQS:
            happenDate = detail.rent.rent_date
            if happenDate not in dayQuantitys:
                if lastDayDetail != None:
                    lastDayDetail = dayQuantitys.setdefault(happenDate, lastDayDetail.copy())
                else:
                    lastDayDetail = dayQuantitys.setdefault(happenDate, dict())
            else:
                lastDayDetail = dayQuantitys[happenDate]

            if detail.product not in lastDayDetail:
                lastDayDetail.setdefault(detail.product, 0)

            lastDayDetail[detail.product] += detail.quantity


        for detail in revertDetailQS:
            happenDate = detail.revert.revert_date
            effectiveDate = happenDate + timedelta(1) # 归还数量要在下一天才被计算

            # 得到本次归还生效日期当天的租借信息，从这天开始向后的每一天的租借信息都要减去本次归还
            # 如果不存在归还生效日期当天的租借信息，则创建一个条目，并复制离当天最近的上一个条目信息，然后进行上述的操作
            if effectiveDate not in dayQuantitys:
                keys = dayQuantitys.keys()
                keys.sort()
                agoDays = [dayQuantitys[k] for k in keys if k < effectiveDate]
                if len(agoDays) > 0:
                    dayQuantitys[effectiveDate] = dayQuantitys.setdefault(effectiveDate, agoDays[-1].copy())
                else:
                    dayQuantitys[effectiveDate] = dayQuantitys.setdefault(effectiveDate, dict())

            keys = dayQuantitys.keys()
            keys.sort()
            afterDays = [dayQuantitys[k] for k in keys if k >= effectiveDate]
            overflow = 0
            for day in afterDays:
                if detail.product in day:
                    day[detail.product] -= (detail.quantity + overflow)
                    if day[detail.product] < 0:
                        overflow = day[detail.product]
                        day[detail.product] = 0
                else:
                    break

        # 计算应收款
        # 首先用今天作为截止日期，计算最近的一个租借日期到截止日期每一天的应收
        # 在将最近一个租借日期作为截止日期，重复上述计算直至遍历所有条目
        keys = dayQuantitys.keys()
        keys.sort()
        # sortedDays = [
            # ('2010-01-01', {product1:10, product2:20}),
            # ('2010-01-02', {product1:10, product2:20}),
        # ]
        sortedDays = [(k, dayQuantitys[k]) for k in keys]
        deadline = timezone.now().date()
        sum = 0
        while len(sortedDays) > 0:
            dayItem = sortedDays.pop();
            if dayItem[0] > deadline:
                continue
            days = (deadline - dayItem[0]).days + 1
            amount = 0
            for p, a in dayItem[1].iteritems():
                amount += (p.unit_price * a)
            amount *= days
            sum += amount
            deadline = dayItem[0] - timedelta(1)

        # logger.debug("sum: %f", sum)
        return sum

    @classmethod
    def clsReceived(cls, **kwarg):
        total = True 
        if kwarg.has_key('customerId'):
            customerId = kwarg['customerId']
            total = False

        result = 0;
        if total:
            qs = Receipt.objects.aggregate(Sum('amount'))
        else:
            qs = Receipt.objects.filter(customer__id=customerId).aggregate(Sum('amount'))

        if qs['amount__sum']:
            result = qs['amount__sum']

        return result

    # 已收
    def received(self):
        return Customer.clsReceived(customerId = self.id)

    # 欠款
    def debt(self):
        self.statist()
        return self.debtValue

    debt.short_description = u'欠款'

    class Meta:
        verbose_name = u"客户"
        verbose_name_plural = u"客户"


class Product(models.Model):
    name = models.CharField(u"产品名称", max_length=200)
    unit_price = models.FloatField(u"单价", help_text=u"元 / 计量单位 / 天")
    M = u"米"
    A = u"个"
    UNIT_CHOICES = (
            (M, M),
            (A, A),
            )
    unit = models.CharField(u"计量单位", 
                            max_length="5",
                            choices=UNIT_CHOICES,
                            default=M)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u"产品"
        verbose_name_plural = u"产品"

# 租借
class Rent(models.Model):
    customer = models.ForeignKey(Customer, verbose_name=u"客户名称")
    rent_date = models.DateField(u"出租日期")
    remarks = models.CharField(u"备注", max_length=500, blank=True)

    #{名称s:{数量d,单位s}, ...}
    def total(self):
        d = {}  #{名称s:{数量d,单位s}, ...}
        for detail in self.rentdetail_set.all():
            if not d.has_key(detail.product.name):
                d[detail.product.name] = {"quantity":0, "unit":detail.product.unit}
            d[detail.product.name]["quantity"] += detail.quantity
        return d

    # 客户姓名 [产品1 10米][产品2 10米]
    def summary(self):
        d = self.total()
        s = self.customer.name + " "
        for k,v in d.items():
            v["customer"] = k
            s += "[%(customer)s %(quantity)8.2f%(unit)s]" % v
        return s
    summary.short_description = u'概要'

    def happenTime(self):
        return self.rent_date
    
    def __unicode__(self):
        return self.summary()

    class Meta:
        verbose_name = u"租借"
        verbose_name_plural = u"租借"

class RentDetail(models.Model):
    rent = models.ForeignKey(Rent, verbose_name=u"租借")
    product = models.ForeignKey(Product, verbose_name=u"产品")
    quantity = models.FloatField(u"数量", default=0)

    def __unicode__(self):
        # 钢管 10米
        return "%s %8.2f%s" % (self.product.name, self.quantity, self.product.unit)

    class Meta:
        verbose_name = u"租借明细"
        verbose_name_plural = u"租借明细"

# 归还
class Revert(models.Model):
    customer = models.ForeignKey(Customer, verbose_name=u"客户名称")
    revert_date = models.DateField(u"归还日期")
    remarks = models.CharField(u"备注", max_length=500, blank=True)

    def total(self):
        d = {}
        for detail in self.revertdetail_set.all():
            if not d.has_key(detail.product.name):
                d[detail.product.name] = {"quantity":0, "unit":detail.product.unit}
            d[detail.product.name]["quantity"] += detail.quantity
        return d
        
    # 客户姓名 [产品1 10米][产品2 10米]
    def summary(self):
        #d = {}
        #for detail in self.revertdetail_set.all():
            #if not d.has_key(detail.product.name):
                #d[detail.product.name] = {"quantity":0, "unit":detail.product.unit}
            #d[detail.product.name]["quantity"] += detail.quantity

        d = self.total()
        s = self.customer.name + " "
        for k,v in d.items():
            v["customer"] = k
            s += "[%(customer)s %(quantity)8.2f%(unit)s]" % v
        return s
    summary.short_description = u'概要'

    def happenTime(self):
        return self.revert_date
    
    def __unicode__(self):
        return self.summary()

    class Meta:
        verbose_name = u"归还"
        verbose_name_plural = u"归还"

class RevertDetail(models.Model):
    revert = models.ForeignKey(Revert, verbose_name=u"归还")
    product = models.ForeignKey(Product, verbose_name=u"产品")
    quantity = models.FloatField(u"数量", default=0)

    def __unicode__(self):
        # 钢管 10米
        return "%s %8.2f%s" % (self.product.name, self.quantity, self.product.unit)

    class Meta:
        verbose_name = u"归还明细"
        verbose_name_plural = u"归还明细"

class Receipt(models.Model):
    customer = models.ForeignKey(Customer, verbose_name=u"客户名称")
    amount = models.FloatField(u"金额", default=0);
    receipt_date = models.DateField(u"收款日期");
    last_modified = models.DateTimeField(auto_now=True);
    remarks = models.CharField(u"备注", max_length=500, blank=True)

    def summary(self):
        # 钢管 10米
        return "%s ￥%s" % (self.customer, self.amount)
    summary.short_description = u'概要'

    def __unicode__(self):
        return self.summary()

    class Meta:
        verbose_name = u"收款"
        verbose_name_plural = u"收款"
