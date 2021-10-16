# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Views for the email app.
"""
import pwd

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import TemplateView, View
from django.views.generic.edit import FormView

import plinth.actions
import plinth.utils
from plinth.views import AppView

from . import aliases as aliases_module
from . import audit, forms


class ExceptionsMixin(View):

    def render_validation_error(self, validation_error, status=400):
        context = self.get_context_data()
        context['error'] = validation_error
        return self.render_to_response(context, status=status)

    def render_exception(self, exception, status=500):
        context = self.get_context_data()
        context['error'] = [str(exception)]
        return self.render_to_response(context, status=status)

    def catch_exceptions(self, function, request):
        try:
            return function(request)
        except ValidationError as validation_error:
            return self.render_validation_error(validation_error)
        except Exception as error:
            return self.render_exception(error)


class EmailServerView(ExceptionsMixin, AppView):
    """Server configuration page"""
    app_id = 'email_server'
    template_name = 'email_server.html'
    audit_modules = ('domain', 'tls', 'rcube')

    def get_context_data(self, *args, **kwargs):
        dlist = []
        for module_name in self.audit_modules:
            self._get_audit_results(module_name, dlist)
        dlist.sort(key=audit.models.Diagnosis.sorting_key)

        context = super().get_context_data(*args, **kwargs)
        context['related_diagnostics'] = dlist
        return context

    def _get_audit_results(self, module_name, dlist):
        try:
            results = getattr(audit, module_name).get()
        except Exception as e:
            title = _('Internal error in {0}').format('audit.' + module_name)
            diagnosis = audit.models.Diagnosis(title)
            diagnosis.critical(str(e))
            diagnosis.critical(_('Check syslog for more information'))
            results = [diagnosis]

        for diagnosis in results:
            if diagnosis.action:
                diagnosis.action = '%s.%s' % (module_name, diagnosis.action)
            if diagnosis.has_failed:
                dlist.append(diagnosis)

    def post(self, request):
        repair_field = request.POST.get('repair')
        module_name, sep, action_name = repair_field.partition('.')
        if not sep or module_name not in self.audit_modules:
            return HttpResponseBadRequest('Bad post data')

        self._repair(module_name, action_name)
        return redirect(request.path)

    def _repair(self, module_name, action_name):
        """Repair the configuration of the given audit module."""
        module = getattr(audit, module_name)
        if not hasattr(module, 'repair_component'):
            return

        reload_list = []
        try:
            reload_list = module.repair_component(action_name)
        except Exception:
            pass

        for service in reload_list:
            # plinth.action_utils.service_reload(service)
            plinth.actions.superuser_run('service', ['reload', service])


class MyMailView(TemplateView):
    template_name = 'my_mail.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        nam = self.request.user.username
        context['has_homedir'] = audit.home.exists_nam(nam)
        return context

    def post(self, request):
        audit.home.put_nam(request.user.username)
        return self.render_to_response(self.get_context_data())


class AliasView(FormView):
    """View to create, list, enable, disable and delete aliases.

    This view has two forms. Form to list (and manage) existing aliases, and a
    form to create a new aliases. When GET operation is used, both forms
    created and template is rendered. When POST operation is used, the form
    posted is detected using hidden form values and the appropriate form is
    initialized for the FormView base class to work with.
    """
    template_name = 'email_alias.html'
    form_classes = (forms.AliasCreateForm, forms.AliasListForm)
    success_url = reverse_lazy('email_server:aliases')

    def __init__(self, *args, **kwargs):
        """Initialize the view."""
        super().__init__(*args, **kwargs)
        self.posted_form = None

    def get_form_class(self):
        """Return form class to build."""
        if self.posted_form == 'create':
            return forms.AliasCreateForm

        return forms.AliasListForm

    def get_form_kwargs(self):
        """Send aliases to list form."""
        kwargs = super().get_form_kwargs()
        if self.posted_form != 'create':
            kwargs['aliases'] = self._get_current_aliases()

        return kwargs

    def _get_uid(self):
        """Return the UID of the user that made the request."""
        return pwd.getpwnam(self.request.user.username).pw_uid

    def _get_current_aliases(self):
        """Return current list of aliases."""
        return aliases_module.get(self._get_uid())

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        if isinstance(context['form'], forms.AliasCreateForm):
            context['create_form'] = context['form']
            aliases = self._get_current_aliases()
            context['list_form'] = forms.AliasListForm(aliases)
        else:
            context['create_form'] = forms.AliasCreateForm()
            context['list_form'] = context['form']

        return context

    def post(self, request, *args, **kwargs):
        """Find which form was submitted before proceeding."""
        self.posted_form = request.POST.get('form')
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Handle a valid submission."""
        if isinstance(form, forms.AliasListForm):
            self._list_form_valid(form)
        elif isinstance(form, forms.AliasCreateForm):
            self._create_form_valid(form)

        return super().form_valid(form)

    def _list_form_valid(self, form):
        """Handle a valid alias list form operation."""
        aliases = form.cleaned_data['aliases']
        action = form.cleaned_data['action']
        uid = self._get_uid()
        if action == 'delete':
            aliases_module.delete(uid, aliases)
        elif action == 'disable':
            aliases_module.disable(uid, aliases)
        elif action == 'enable':
            aliases_module.enable(uid, aliases)

    def _create_form_valid(self, form):
        """Handle a valid create alias form operation."""
        aliases_module.put(self._get_uid(), form.cleaned_data['alias'])


class DomainsView(FormView):
    """View to allow editing domain related settings."""
    template_name = 'form.html'
    form_class = forms.DomainsForm
    prefix = 'domain'
    success_url = reverse_lazy('email_server:domains')

    def get_initial(self):
        """Return the initial values to populate in the form."""
        initial = super().get_initial()
        initial.update(audit.domain.get_domain_config())
        return initial

    def get_context_data(self, **kwargs):
        """Add the title to the document."""
        context = super().get_context_data(**kwargs)
        context['title'] = _('Domains')
        return context

    def form_valid(self, form):
        """Update the settings for changed domain values."""
        old_data = form.initial
        new_data = form.cleaned_data
        config = {}
        for key in form.initial:
            if old_data[key] != new_data[key]:
                config[key] = new_data[key]

        if config:
            try:
                audit.domain.set_keys(config)
                messages.success(self.request, _('Configuration updated'))
            except Exception:
                messages.success(self.request,
                                 _('Error updating configuration'))
        else:
            messages.info(self.request, _('Setting unchanged'))

        return super().form_valid(form)


class XmlView(TemplateView):
    template_name = 'email_autoconfig.xml'

    def render_to_response(self, *args, **kwargs):
        kwargs['content_type'] = 'text/xml; charset=utf-8'
        response = super().render_to_response(*args, **kwargs)
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        return context
