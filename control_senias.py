# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from datetime import datetime , timedelta ,  date
from dateutil import parser

from openerp import models, fields, api ,  SUPERUSER_ID
from openerp import tools


from openerp.tools.translate import _
import re
import logging

import requests
from lxml import etree

_logger = logging.getLogger(__name__)



class control_senias(models.Model):

    _name = 'control.senias'
    _description = 'Control de señas'

    _inherit = ['mail.thread']

    @api.one
    def _create_senia_sequence(self):
     self.check_sequence_id = self.env['ir.sequence'].sudo().create({
         'name': self.name ,
         'implementation': 'no_gap',
         'padding': 5,
         'number_increment': 1,
         'company_id': self.company_id.id,
     })

    name = fields.Char('Numero', default='/')
    user_id = fields.Many2one('res.users',string='usuario')
    partner_id = fields.Many2one('res.partner',string='cliente')
    amount = fields.Float(string='Monto')

    section_id = fields.Many2one('crm.case.section',string='Equipo')

    validity = fields.Date('Validez',track_visibility='onchange')

    control_senias_items_ids = fields.One2many('control.senias.items','control_senias_id',string='items')
    state = fields.Selection([('draft','Borrador'),('cancel','Cancelado'),('active','Valida'),('partial','Parcial'),('end','Finalizada')],compute="_compute_control_senias_state",default='draft' )

    '''
    @api.model
    def create(self, vals):
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('control.senias') or '/'

                return super(control_senias, self).create(vals)
    '''

    @api.multi
    @api.depends('control_senias_items_ids')
    def _compute_control_senias_state(self):
        for  control in self:
            states = set([x.state for x in control.control_senias_items_ids])
            if len(states) == 1 :
                control.state=list(states)[0]
            else :
                control.state = 'partial'


    @api.model
    def create(self,vals) :

        vals['message_follower_ids'] = []

        blancoamor_logistic = self.env['ir.model.data'].get_object('ba_conf', 'blancoamor_logistic')
        for user in blancoamor_logistic.users :
            vals['message_follower_ids'].append(user.partner_id.id)

        rec = super(control_senias, self).create(vals)   
        return rec        

    @api.model
    def cancel_old_senias(self):

        args=[('validity' ,'<', date.today()),('state','in',['draft','active'])]
        ids=self.search(args)
        ids.write({'state':'end'})



    @api.one
    def cancel(self):
        user = self.env['res.users'].browse(self.env.uid)
        if user.has_group('ba_conf.blancoamor_logistic'):
            self['state']='cancel'

    @api.one
    def active(self):
        user = self.env['res.users'].browse(self.env.uid)
        team=self.env['crm.case.section'].search([('member_ids','=',self.env.uid)],limit=1)
        is_alter=False

        if team and 'warehouse_id' in team:
            warehouse_ids=[x.id for x in team.warehouse_id]
            for item in self.control_senias_items_ids:
                if item.warehouse_id.id in warehouse_ids:
                    item.write({'state':'active'})
                    is_alter = True
        if is_alter : 
            self['state']='active'


        '''
        if user.has_group('ba_conf.blancoamor_logistic'):
            self['state']='active'
            team=self.env['crm.case.section'].browse(LOGISTIC_TEAM)
            warehouse_ids=[x.id for x in team.warehouse_id]
            for item in self.control_senias_items_ids:
                if item.warehouse_id.id in warehouse_ids:
                    item.write({'state':'active'})
        else :
            team=self.env['crm.case.section'].search([('members_id','=',self.env.uid)])
            if team and warehouse_id in team:
                warehouse_ids=[x.id for x in team.warehouse_id]
                for item in self.control_senias_items_ids:
                    if item.warehouse_id in warehouse_ids:
                        item.write({'state':'active'})
        '''
            





class control_senias_items(models.Model):

    _name = 'control.senias.items'
    _description = 'Control de senias'

    '''
    @api.depends('products_product_id','control_senias_id')
    def _default_warehouse_id(self):
        if self.products_product_id.product_tmpl_id.business_unit_id.name == 'Blanqueria':
            return 1
    '''

    control_senias_id= fields.Many2one('control.senias' , ondelete="cascade" )
    state = fields.Selection([('draft','Borrador'),('cancel','Cancelado'),('active','Valida'),('end','Finalizada')],default='draft')
    validity = fields.Date('Validez',related='control_senias_id.validity' )

    products_product_id= fields.Many2one('product.product')
    supplier_id= fields.Many2one('res.partner',compute='_compute_supplier',store=True)

    reserved_qty =fields.Float('Cantidad')
    stock_qty =fields.Float('Cantidad en stock',related='products_product_id.virtual_available')
    warehouse_id = fields.Many2one('stock.warehouse', string='Deposito donde reserva')

    @api.multi
    @api.depends('products_product_id')
    def _compute_supplier(self):
        for line in self : 
            if len(line.products_product_id.seller_ids) :
                line.supplier_id = line.products_product_id.seller_ids[0].name

    @api.model
    def cancel_old_senias(self):

        args=[('validity' ,'<', date.today()),('state','in',['draft','active'])]
        ids=self.search(args)
        ids.write({'state':'end'})

