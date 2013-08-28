import logging
import traceback
from Acquisition import aq_inner
from OFS.SimpleItem import SimpleItem
from zope.component import adapts
from zope.component.interfaces import ComponentLookupError
from zope.interface import Interface, implements
from zope.formlib import form
from zope import schema
from smtplib import SMTPException
from plone.app.contentrules.browser.formhelper import AddForm, EditForm
from plone.contentrules.rule.interfaces import IRuleElementData, IExecutable
from plone.stringinterp.interfaces import IStringInterpolator
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone import PloneMessageFactory as _
from Products.MailHost.MailHost import MailHostError
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from collective.contentrules.mailadapter.interfaces import IRecipientsResolver

logger = logging.getLogger("collective.contentrules.mailadapter")

class IMailAction(Interface):
    """Definition of the configuration available for a mail action
    """
    subject = schema.TextLine(title=_(u"Subject"),
                              description=_(u"Subject of the message"),
                              required=True)
    source = schema.TextLine(title=_(u"Email source"),
                             description=_("The email address that sends the \
email. If no email is provided here, it will use the portal from address."),
                             required=False)
    message = schema.Text(title=_(u"Message"),
                          description=_(u"Type in here the message that you \
want to mail. Some defined content can be replaced: ${title} will be replaced \
by the title of the item. ${url} will be replaced by the URL of the item."),
                          required=True)

class MailAction(SimpleItem):
    """
    The implementation of the action defined before
    """
    implements(IMailAction, IRuleElementData)

    subject = u''
    source = u''
    message = u''

    element = 'collective.actions.Mail'

    @property
    def summary(self):
        return _(u"Email report sent")

class MailActionExecutor(object):
    """The executor for this action.
    """
    implements(IExecutable)
    adapts(Interface, IMailAction, Interface)

    def __init__(self, context, element, event):
        self.context = context
        self.element = element
        self.event = event

    def __call__(self):
        # get the recipients
        recipient_resolver = IRecipientsResolver(self.event.object)

        if recipient_resolver:
            recipients = recipient_resolver.recipients()

        mailhost = aq_inner(self.context).MailHost
        if not mailhost:
            raise ComponentLookupError, 'You must have a Mailhost utility to \
execute this action'

        urltool = getToolByName(aq_inner(self.context), "portal_url")
        portal = urltool.getPortalObject()
        email_charset = portal.getProperty('email_charset')

        obj = self.event.object

        interpolator = IStringInterpolator(obj)

        source = self.element.source
        if source:
            source = interpolator(source).strip()

        if not source:
            # no source provided, looking for the site wide from email
            # address
            from_address = portal.getProperty('email_from_address')
            if not from_address:
                raise ValueError, 'You must provide a source address for this \
action or enter an email in the portal properties'

            from_name = portal.getProperty('email_from_name')
            source = "%s <%s>" % (from_name, from_address)

        # prepend interpolated message with \n to avoid interpretation
        # of first line as header
        message = "\n%s" % interpolator(self.element.message)

        subject = interpolator(self.element.subject)

        for email_recipient in recipients:
            mailhost.secureSend(message, email_recipient, source,
                                subject=subject, subtype='plain',
                                charset=email_charset, debug=False,
                                )

        return True

class MailAddForm(AddForm):
    """
    An add form for the mail action
    """
    form_fields = form.FormFields(IMailAction)
    label = _(u"Add Mail Action")
    description = _(u"A mail action can mail different recipient.")
    form_name = _(u"Configure element")

    # custom template will allow us to add help text
    template = ViewPageTemplateFile('mail.pt')

    def create(self, data):
        a = MailAction()
        form.applyChanges(a, self.form_fields, data)
        return a

class MailEditForm(EditForm):
    """
    An edit form for the mail action
    """
    form_fields = form.FormFields(IMailAction)
    label = _(u"Edit Mail Action")
    description = _(u"A mail action can mail different recipient.")
    form_name = _(u"Configure element")

    # custom template will allow us to add help text
    template = ViewPageTemplateFile('mail.pt')
