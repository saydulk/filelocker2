import cherrypy
import logging
from Cheetah.Template import Template
from lib.SQLAlchemyTool import session
import AccountController
from lib.Formatters import *
from lib.Models import *
from lib import Mail
__author__="wbdavis"
__date__ ="$Sep 25, 2011 9:28:23 PM$"

class ShareController:

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def create_user_shares(self, fileIds, userId=None, notify="no", cc="no", format="json", **kwargs):
        user, sMessages, fMessages  = (cherrypy.session.get("user"), [], [])
        fileIds = split_list_sanitized(fileIds)
        userId = strip_tags(userId) if targetId is not None and targetId != "" else None
        notify = True if notify.lower() == "yes" else False
        try:
            sharedFiles = []
            for fileId in fileIds:
                flFile = session.query(File).filter(File.id==fileId).one()
                shareUser = AccountController.get_user(userId)
                if flFile.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                    session.add(UserShare(user_id=userId, file_id=fileId))
                    session.commit()
                    sharedFiles.append(flFile)
                else:
                    fMessages.append("You do not have permission to share file with ID: %s" % str(flFile.id))
            if notify:
                Mail.notify(get_template_file('share_notification.tmpl'),{'sender':user.email,'recipient':shareUser.email, 'ownerId':user.id, 'ownerName':user.display_name, 'files':sharedFiles, 'filelockerURL': config['root_url']})
                session.add(AuditLog(user.userId, "Sent Email", "%s has been notified via email that you have shared a file with him or her." % (shareUser.email)))
                session.commit()
            sMessages.append("Shared file(s) successfully")
        except Exception, e:
            fMessages.append(str(e))
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def delete_user_shares(self, fileIds, userId, format="json"):
        user, sMessages, fMessages = (cherrypy.session.get("user"), [], [])
        fileIds = split_list_sanitized(fileIds)
        for fileId in fileIds:
            try:
                flFile = session.query(File).filter(File.id==fileId).one()
                if flFile.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                    ps = session.query(UserShare).filter(UserShare.user_id == userId and UserShare.file_id == flFile.id).scalar()
                    if ps is not None:
                        session.delete(ps)
                        session.add(AuditLog(user.id, "Delete User Share", "You stopped sharing file %s with %s" % (flFile.name, userId)))
                        session.commit()
                else:
                    fMessages.append("You do not have permission to modify shares for file with ID: %s" % str(flFile.id))
            except Exception, e:
                session.rollback()
                fMessages.append("Problem deleting share for file: %s" % str(e))
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def create_group_shares(self, fileIds, groupId, notify="no", format="json"):
        user, sMessages, fMessages  = (cherrypy.session.get("user"), [], [])
        fileIds = split_list_sanitized(fileIds)
        groupId = strip_tags(groupId) if groupId is not None and groupId != "" else None
        notify = True if notify.lower() == "yes" else False
        try:
            if groupId is not None:
                group = session.query(Group).filter(Group.id==groupId).one()
                if group.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                    sharedFiles = []
                    for fileId in fileIds:
                        flFile = session.query(File).filter(File.id == fileId).one()
                        if flFile.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                            session.add(GroupShare(group_id=groupId, file_id=fileId))
                            sharedFiles.append(flFile)
                        else:
                            fMessages.append("You do not have permission to share file with ID: %s" % fileId)
                    sMessages.append("Shared file(s) successfully")
                else:
                    fMessages.append("You do not have permission to share with this group")
                session.commit()
                if notify:
                    for groupMember in group.members:
                        Mail.notify(get_template_file('share_notification.tmpl'),{'sender':user.email,'recipient':shareUser.email, 'ownerId':user.id, 'ownerName':user.display_name, 'files':sharedFiles, 'filelockerURL': config['root_url']})
                        session.add(AuditLog(user.id, "Sent Email", "%s has been notified via email that you have shared a file with him or her." % (shareUser.email)))
                        session.commit()
        except Exception, e:
            session.rollback
            fMessages.append(str(e))
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def delete_group_shares(self, fileIds, groupId, format="json"):
        user, sMessages, fMessages = (cherrypy.session.get("user"), [], [])
        fileIds = split_list_sanitized(fileIds)
        for fileId in fileIds:
            try:
                group = session.query(Group).filter(Group.id==groupId).one()
                if group.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                    flFile = session.query(File).filter(File.id==fileId).one()
                    if flFile.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                        share = session.query(GroupShare).filter(GroupShare.group_id == groupId and GroupShare.file_id == flFile.id).scalar()
                        if share is not None:
                            session.delete(share)
                            session.add(AuditLog(user.id, "Delete Group Share", "You stopped sharing file %s with group %s" % (flFile.name, group.name)))
                            session.commit()
                    else:
                        fMessages.append("You do not have permission to modify shares for file with ID: %s" % str(flFile.id))
                else:
                    fMessages.append("You do not have permission delete shares with this group")
            except Exception, e:
                session.rollback()
                fMessages.append("Problem deleting share for file: %s" % str(e))
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def get_files_shared_with_user(self, fileIdList=None, format="json", **kwargs):
        #Determine which files are shared with the user
        user, sMessages, fMessages, sharedFiles = (cherrypy.session.get("user"), [], [], [])
        try:
            fileIds = []
            for flFile in get_files_shared_with_user(user):
                if flFile.id not in fileIds:
                    sharedFiles.append(flFile.get_dict())
                    fileIds.append(flFile.id)
#             TODO: Implement Share Hiding
#            if fl.is_share_hidden(user, sharedFile.fileId) is False:
#                sharedFilesList.append(sharedFile)
        except Exception, e:
            fMessages.append(str(e))
        return fl_response(sMessags, fMessages, format, data=sharedFiles)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def create_attribute_shares(self, fileIds, attributeId, format="json", **kwargs):
        user, sMessages, fMessages  = (cherrypy.session.get("user"), [], [])
        try:
            userShareableAttributes, permission = AccountController.get_shareable_attributes_by_user(user), False
            for attribute in userShareableAttributes:
                if attributeId == attribute.id:
                    permission = True
                    break
            if permission:
                fileIds = split_list_sanitized(fileIds)
                for fileId in fileIds:
                    session.add(AttributeShare(file_id=fileId, attribute_id=attributeId))
                sMessages.append("Successfully shared file(s) with users having the %s attribute" % attributeId )
            else:
                fMessages.append("You do not have permission to share with this attribute")
        except Exception, e:
            fMessages.append(str(e))
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def delete_attribute_shares(self, fileIds, attributeId, format="json", **kwargs):
        user, sMessages, fMessages  = (cherrypy.session.get("user"), [], [])
        try:
            userShareableAttributes, permission = AccountController.get_shareable_attributes_by_user(user), False
            for attribute in userShareableAttributes:
                if attributeId == attribute.id:
                    permission = True
                    break
            if permission:
                fileIdList = split_list_sanitized(fileIds)
                for fileId in fileIdList:
                    share = session.query(AttributeShare).filter(AttributeShare.attribute_id==attributeId and rivateAttributeShare.fileId==fileId).one()
                    session.delete(share)
                sMessages.append("Successfully unshared file(s) with users having the %s attribute") % attributeId
            else:
                fMessages.append("You do not have permission to delete attribute shares for this attribute")
        except Exception, e:
            fMessages.append(str(e))
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def create_public_share(self, fileIds, expiration, shareType, notifyEmails, cc="no", format="json", **kwargs):
        user, sMessages, fMessages, shareId = (cherrypy.session.get("user"), [], [], None)
        config = cherrypy.request.app.config['filelocker']
        fileIds = split_list_sanitized(fileIds)
        cc = True if cc == "yes" else False
        try:
            try:
                expiration = datetime.datetime(*(time.strptime(strip_tags(expiration), "%m/%d/%Y")[0:6]))
            except Exception, e:
                raise Exception("Invalid expiration date format. Date must be in mm/dd/yyyy format.")
            if expiration is None or expiration == "":
                raise Exception("Public shares must have a valid expiration date")

            shareType != "single" if shareType != "multi" else "multi"
            ps = PublicShare(date_expires=expiration, reuse=shareType)
            if (kwargs.has_key("password") and kwargs['password']!=""):
                ps.set_password(kwargs['password'])
            elif shareType=="multi":
                raise Exception("You must specify a password for public shares that don't expire after 1 use")
            ps.generate_share_id()
            session.add(ps)
            sharedFiles = []
            for fileId in fileIds:
                flFile = session.query(File).filter(File.id==fileId).one()
                if flFile.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                    ps.files.append(flFile)
                    session.commit()
                    sharedFiles.append(flFile)
                else:
                    fMessages.append("You do not have permission to share file with ID: %s" % str(flFile.id))
            notifyEmailList = split_list_sanitized(notifyEmails)
            if cc:
                notifyEmailList.append(user.email)
            for recipient in notifyEmailList:
                Mail.notify(get_template_file('public_share_notification.tmpl'), {'sender':user.email, 'recipient':recipient, 'files':sharedFiles, 'ownerId':user.id, 'ownerName': user.display_name, 'shareId':ps.id, 'filelockerURL':config['root_url']})
            if len(notifyEmailList) > 0:
                session.add(AuditLog(user.id, "Email Sent", "Email notifications about a public share were sent to the following addresses: %s" % str(",".join(notifyEmailList))))
            session.add(AuditLog(user.id, "Create Public Share", "File(s) publicly shared."))
            session.commit()
            sMessages.append("Files shared successfully")
        except Exception, e:
            session.rollback()
            fMessages.append(str(e))
            logging.error("[%s] [create_public_share] [Unable to create public share: %s]" % (user.id, str(e)))
        return fl_response(sMessages, fMessages, format, data=ps.id)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def delete_public_share(self, shareId, format="json", **kwargs):
        #TODO: Public sharing has to be redone to accomodate multi-shares
        user, sMessages, fMessages = (cherrypy.session.get("user"), [], [])
        shareId = strip_tags(shareId)
        try:
            ps = session.query(PublicShare).filter(PublicShare.id == shareId).one()
            if ps.owner_id == user.id or AccountController.user_has_permission(user, "admin"):
                session.delete(ps)
                session.add(AuditLog(user.id, "Delete Public Share", "You stopped sharing files publicly via URL using share ID: %s" % str(ps.id)))
                session.commit()
                sMessages.append("Successfully unshared files")
            else:
                fMessages.append("You do not have permission to modify share ID: %s" % str(ps.id))
        except Exception, e:
            fMessags.append(str(e))
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def unhide_all_shares(self, format="json"):
        user, fl, sMessages, fMessages = (cherrypy.session.get("user"), cherrypy.thread_data.flDict['app'], [], [])
        try:
            fl.unhide_all_private_shares(user)
            sMessages.append("Successfully unhid shares")
        except FLError, fle:
            fMessages.extend(fle.failureMessages)
            sMessages.extend(fle.successMessages)
        return fl_response(sMessages, fMessages, format)

    @cherrypy.expose
    @cherrypy.tools.requires_login()
    def hide_share(self, fileIds, format="json"):
        user, fl, sMessages, fMessages = (cherrypy.session.get("user"), cherrypy.thread_data.flDict['app'], [], [])
        fileIds = split_list_sanitized(fileIds)
        for fileId in fileIds:
            try:
                fl.hide_private_share(user, fileId)
                sMessages.append("Successfully hid share. Unhide shares in Account Settings.")
            except FLError, fle:
                fMessages.extend(fle.failureMessages)
                sMessages.extend(fle.successMessages)
        return fl_response(sMessages, fMessages, format)


def get_files_shared_with_user(user):
    sharedFiles = []
    for share in session.query(UserShare).filter(UserShare.user_id==user.id).all():
        for flFile in share.files:
            sharedFiles.append(flFile)
    for group in user.groups:
        for share in group.group_shares:
            for flFile in share.files:
                sharedFiles.append(flFile)
    return sharedFiles
def get_user_shareable_attributes(user):
    """
    This function gets the attributes that a user has permission to share with.

    Examples of this would be a teacher for a class being able to share with all users
    who have the class as an attribute"""
    attributeList = []
    allAttributes = session.query(Attribute).all()
    if AccountController.user_has_permission(user, "admin"):
        attributeList = allAttributes
    else:
        for attribute in allAttributes:
            attributePermissionId = "(attr)%s" % attribute.attributeId
            if AccountController.user_has_permission(user, attributePermissionId):
                attributeList.append(attribute)
    return attributeList

def get_files_shared_with_user_by_attribute(user):
    """Builds a dictionary keyed by attribute id with values that are lists of files shared by this attribute"""
    attributeShareDictionary = {}
    for attributeId in user.attributes:
        attribute = session.query(Attribute).filter(Attribute.id==attributeId).scalar() #Do this to ensure this attribute is even recognized by the system
        if attribute is not None:
            for attributeShare in session.query(AttributeShare).filter(AttributeShare.attribute_id==attribute.id).all():
                if attributeShareDictionary.has_key(attributeShare.attribute_id)==False:
                    attributeShareDictionary[attributeShare.attribute_id] = []
                attributeShareDictionary[attributeShare.attribute_id].append(attributeShare.flFile)
    return attributeShareDictionary
    
if __name__ == "__main__":
    print "Hello";