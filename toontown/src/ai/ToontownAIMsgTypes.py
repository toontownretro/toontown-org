# This file holds Toontown specific AI message types

from otp.ai.AIMsgTypes import *

TTAIMsgName2Id = {
 'DBSERVER_GET_ESTATE' : 1040,
 'DBSERVER_GET_ESTATE_RESP' : 1041,
 # RAU I think 1042 is not being used elsewhere.
 'PARTY_MANAGER_UD_TO_ALL_AI' : 1042,
 'IN_GAME_NEWS_MANAGER_UD_TO_ALL_AI' : 1043,
 'WHITELIST_MANAGER_UD_TO_ALL_AI' : 1044,
 }

#DBSERVER_GET_ESTATE =                                   1040
#DBSERVER_GET_ESTATE_RESP =                              1041

# RAU I think 1042 is not being used elsewhere.
#PARTY_MANAGER_UD_TO_ALL_AI =                            1042
#IN_GAME_NEWS_MANAGER_UD_TO_ALL_AI =                     1043

if not isClient():
    print 'EXECWARNING ToontownAIMsgTypes: %s' % TTAIMsgName2Id
    printStack()
for name, value in TTAIMsgName2Id.items():
    exec '%s = %s' % (name, value)

del name
del value

DBSERVER_PET_OBJECT_TYPE = 5
