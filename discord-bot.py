import discord
import os.path
from discord.ext import tasks
from discord.ext import commands
import requests
from datetime import datetime
from dateutil import parser
import config
import json
import time
bot = commands.Bot(command_prefix='$')

@bot.event
async def on_ready():
    #check for stored credentials
    #if found, try to auth
    print('We have logged in as {0.user}'.format(bot))
    await loadData()
    await loadSubscription()
    
    #if config.stored_username is not None:
        #try_auth(config.stored_username, config.stored_password)
    

#@client.event
#async def on_message(message):
#    if message.author == client.user:
#        return

#    if message.content.startswith('$hello'):
 #       await message.channel.send('Hello!')


@bot.command()
async def auth(ctx, username, password):
    
    #try to auth
    await ctx.send("trying to auth")
    status = await try_auth(username, password)
    if status == "Error":
        await ctx.send("Error authenticating")
    else:
        await ctx.send("Login Successful!")
    await ctx.message.delete()



async def try_auth(username, password):
#make request
    payload = { 'username':username, 'password':password }
    login = await apiCall("/auth/login", "POST", payload)
    if 'Error' not in login:
        config.stored_password = password
        config.stored_username = username
        config.token = login['token']
        config.last_updated = datetime.now()
        config.isAuthed = True

        await storeData()
        return "Success"
    else:
        #await ctx.send("Login Error: {0}".format(login['Error']))
        return "Error"


@bot.command()
async def subscribe(ctx, args):
    if config.token is None:
        await ctx.send("Error: No logged-in user")
    else:
        try:
            #log("blah")
            config.guild = ctx.message.guild
            #log("blah 2")
            if ctx.message.channel_mentions is None:
                config.channel = ctx.message.channel
            else:
                config.channel = ctx.message.channel_mentions[0]
            #log("blah 3")
            if ctx.message.role_mentions is None:
                config.role = []
            else:
                config.role = ctx.message.role_mentions[0]
            #log("blah 4")
            config.subscription_active = True

            await storeSubscription()
            
            if subscriptionLoop.is_running():
                subscriptionLoop.restart()
            else:
                await subscriptionLoop.start()

            await ctx.send("Subscription created successfully")
        except Exception as e:
            #print(str(e))
            await ctx.send("Uncaught Error"+ str(e))

@bot.command()
async def list_sub(ctx, list):
    if config.token is None:
        await ctx.send("Error: No logged-in user")
    else:
        try:
            #print("blah")
            list = list
            print(list)
            guild = ctx.message.guild
            #print("blah 2")
            if ctx.message.channel_mentions is None:
                channel = ctx.message.channel
            else:
                channel = ctx.message.channel_mentions[0]
            #print("blah 3")
            if ctx.message.role_mentions is None:
                role = []
            else:
                role = ctx.message.role_mentions[0]


            await add_list(list, guild, channel, role, True, True, [])
            #print(config.subscribedLists)
            print(1)
            await storeSubscription()
            print(2)
            if subscriptionLoop.is_running():
                subscriptionLoop.restart()
            else:
                await subscriptionLoop.start()

            await ctx.send("Subscription created successfully")
        except Exception as e:
            print(str(e))
            await ctx.send("Uncaught Error"+ str(e))


async def add_list(guid, guild, channel, role, active, firstRun, chapterCache):
    listdef = {"guid": guid, "guild": guild, "channel": channel, "role": role, "firstRun": firstRun, "subscription_active": active, "chapterCache": chapterCache}
    
    if config.subscribedLists is []:
        config.subscribedLists.append(listdef)
    elif guid in [x['guid'] for x in config.subscribedLists]:
        config.subscribedLists = [listdef if x['guid'] == guid else x for x in config.subscribedLists]
    else:
        config.subscribedLists.append(listdef)

async def update_list(list):
    if config.subscribedLists is []:
        config.subscribedLists.append(list)
    elif list['guid'] in [x['guid'] for x in config.subscribedLists]:
        config.subscribedLists = [list if x['guid'] == list['guid'] else x for x in config.subscribedLists]
    else:
        config.subscribedLists.append(list)

async def removelist(guid):
    config.subscribedLists = [x for x in config.subscribedLists if not x['guid'] == guid]

@bot.command()
async def remove_list(ctx, arg):
    await removelist(arg)
    await storeSubscription()
    
    await ctx.send("Successfully unsubscribed from list")

@bot.command()
async def unsubscribe(ctx, temp=None):
    config.firstRun = True
    config.subscription_active = False
    await storeSubscription()
    subscriptionLoop.stop()
    await ctx.send("Successfully unsubscribed")

@bot.command()
async def ignore_group(ctx, arg):
    if arg not in config.ignoredGroups:
        config.ignoredGroups.append(arg);
    await storeSubscription()
    await ctx.send("Ignored!")
    await ctx.send("Ignored Groups: {0}".format(str(config.ignoredGroups)))

@bot.command()
async def unignore_group(ctx, arg):
    if arg in config.ignoredGroups:
        config.ignoredGroups.remove(arg);
    await storeSubscription()
    await ctx.send("Unignored!")
    await ctx.send("Ignored Groups: {0}".format(str(config.ignoredGroups)))

@bot.command()
async def clear_ignored_groups(ctx):
    config.ignoredGroups = []
    await storeSubscription()
    await ctx.send("Cleared!")
    await ctx.send("Ignored Groups: {0}".format(str(config.ignoredGroups)))

@bot.command()
async def ignore_uploader(ctx, arg):
    if arg not in config.ignoredUploaders:
        config.ignoredUploaders.append(arg);
    await storeSubscription()
    await ctx.send("Ignored!")
    await ctx.send("Ignored Uploaders: {0}".format(str(config.ignoredUploaders)))

@bot.command()
async def unignore_uploader(ctx, arg):
    if arg in config.ignoredUploaders:
        config.ignoredUploaders.remove(arg);
    #config.chapterCache = []
    #print('unsubscribed')
    await storeSubscription()
    await ctx.send("Ignored!")
    await ctx.send("Ignored Uploaders: {0}".format(str(config.ignoredUploaders)))

@bot.command()
async def clear_ignored_uploaders(ctx):
    config.ignoredUploaders = []

    await storeSubscription()
    await ctx.send("Cleared!")
    await ctx.send("Ignored Uploaders: {0}".format(str(config.ignoredUploaders)))

@bot.command()
async def force_update(ctx):
    messages = await getFeedChapters(0)
    if messages is not None:
        for m in messages:
            discordMessage = "{0}\n{1}".format(config.role.mention, m)
            await config.channel.send(discordMessage)

@bot.command()
async def substatus(ctx):
    await ctx.send("Guild: {0}\nChannel: {1}\nrole: {2}\nfirstRun: {3}\nisActive: {4}".format(str(config.guild.id),
    str(config.channel.id),str(config.role.id),config.firstRun, config.subscription_active))

@bot.command()
async def resub(ctx):
    auth_status = await try_auth(config.stored_username, config.stored_password)
    if auth_status == "Error":
        subscriptionLoop.stop()
        time.sleep(300)
        resub(ctx)
    else:
        config.isAuthed = True
        config.subscription_active = True
        if subscriptionLoop.is_running():
            subscriptionLoop.restart()
        else:
            await subscriptionLoop.start()
    

#set loop start
@tasks.loop(seconds = 360)
async def subscriptionLoop():
    if config.subscription_active is None:
        #log("No Active Subscription")
        return
    #print("getting chapters")
    messages = await getFeedChapters(0)
    if messages is not None:
        for m in messages:
            discordMessage = "{0}\n{1}".format(config.role.mention, m)
            await config.channel.send(discordMessage)
    
    for list in config.subscribedLists:
        messages2 = await getListChapters(list, 0)
        if messages2 is not None:
            for m in messages2:
                discordMessage = "{0}\n{1}".format(list['role'].mention, m)
                await list['channel'].send(discordMessage)
    await storeSubscription()
    

    
#get feed chapters
#send messages to specified channel, mentioning the specified role
#@subscriptionLoop.before_loop
#async def before_my_task(self):
    #await self.wait_until_ready() # wait until the bot logs in
    #print("ready to start")



async def getFeedChapters(offset = 0):
    #check config.isAuthed
    limit = 30
    if config.firstRun:
        limit = 1
    #print("awaiting token")
    is_go = await validateTokens()
    if is_go is False:
        config.isAuthed = False
        config.subscription_active = False
        subscriptionLoop.stop()
        return ["Error authenticating, please re-authenticate"]
    #get data from feed
    #print("getting data from feed")
    payload = {"limit":limit, "translatedLanguage[]":"en", "offset":offset,"order[publishAt]":"desc","includes[]":["manga","scanlation_group"],
    "excludedGroups[]":config.ignoredGroups,"excludedUploaders[]":config.ignoredUploaders, "contentRating[]":["safe","suggestive","erotica","pornographic"]}
    feed = await apiCall("/user/follows/manga/feed", "GET",payload)
    #print("data received from feed")
    #got data
    #print(feed)
    if 'Error' in feed:
        #print("Error received")
        return ["Error in results"]
    #print(feed)
    chapters = feed['data']
    broken = False
    tempfeed = []
    messages = []
    #print("starting chapter loop")
    #print(chapters)
    for chapter in chapters:
        #workaround for MangaPlus - ignore chapter if publishAt is greater than current time.
        #if parser.parse(chapter['attributes']['publishAt'],ignoretz=True) > datetime.now():
            #continue
        #check IDs against stored chapters
        if chapter['id'] in config.chapterCache:
            broken = True
            break
        else:
            #print(chapter)
            #if not found, push manga and group names to lists, and push manga to temp
            chapter_obj = {"id":chapter["id"], "volume":chapter['attributes']['volume'],
             "chapter":chapter['attributes']['chapter'],"title":chapter['attributes']['title']}
            if chapter_obj["volume"] is None:
                chapter_obj["volume"] = "Unspecified"
            if chapter_obj["title"] is None:
                chapter_obj["title"] = "Chapter "+chapter_obj["chapter"]
            
            

            for r in chapter['relationships']:
                if r['type'] == "manga":
                    if 'en' in r['attributes']['title']:
                        chapter_obj["manga"] = r['attributes']['title']['en']
                    elif 'altTitles' in r['attributes']:
                        chapter_obj["manga"] = ""
                        for item in r['attributes']['altTitles']:
                            if 'en' in item:
                                chapter_obj["manga"] = item['en']
                                break
                        if chapter_obj["manga"] == "":
                            chapter_obj["manga"] = "No English Title"
                    else:
                        chapter_obj["manga"] = "No English Title"
                elif r['type'] == "scanlation_group":
                    chapter_obj["group"] = r['attributes']['name']
            if 'group' not in chapter_obj:
                chapter_obj["group"] = "No Group"
            tempfeed.append(chapter_obj)
    #if last chapter wasn't found, get more from feed.
    if broken is False and config.firstRun is False:
        more_messages = await getFeedChapters(offset+limit)
        messages.append(more_messages)

    #if temp list is not empty
    if tempfeed is not None:
        #iterate over temp
        tempfeed.reverse()
        for chap in tempfeed:
            #build messages and store
            message = "**{0}**\n".format(chap["manga"])
            message += "Volume {0} Chapter {1}\n".format(chap["volume"], chap["chapter"])
            message += "Title: {0} Group: {1}\n".format(chap["title"], chap["group"])
            message += "https://mangadex.org/chapter/{0}".format(chap["id"])
            messages.append(message)
            #push chapter to memory
            config.chapterCache.insert(0,chap["id"])
        #trim memory
        del config.chapterCache[10:]

    if config.firstRun == True:
        config.firstRun = False

    #return message strings
    return messages


async def getListChapters(list, offset = 0):
    #check config.isAuthed
    limit = 30
    if list['firstRun']:
        limit = 1
    #print("awaiting token")
    is_go = await validateTokens()
    if is_go is False:
        config.isAuthed = False
        list['subscription_active'] = False
        subscriptionLoop.stop()
        return ["Error authenticating, please re-authenticate"]
    #get data from feed
    #print("getting data from feed")
    payload = {"limit":limit, "translatedLanguage[]":"en", "offset":offset,"order[publishAt]":"desc","includes[]":["manga","scanlation_group"],
    "excludedGroups[]":config.ignoredGroups,"excludedUploaders[]":config.ignoredUploaders, "contentRating[]":["safe","suggestive","erotica","pornographic"]}
    feed = await apiCall("/list/{0}/feed".format(list['guid']), "GET",payload)
    #print("data received from feed")
    #got data
    #print(feed)
    if 'Error' in feed:
        #print("Error received")
        return ["Error in results"]
    #print(feed)
    chapters = feed['data']
    broken = False
    tempfeed = []
    messages = []
    #print("starting chapter loop")
    #print(chapters)
    for chapter in chapters:
        #workaround for MangaPlus - ignore chapter if publishAt is greater than current time.
        #if parser.parse(chapter['attributes']['publishAt'],ignoretz=True) > datetime.now():
            #continue
        #check IDs against stored chapters
        if chapter['id'] in list['chapterCache']:
            broken = True
            break
        else:
            #print(chapter)
            #if not found, push manga and group names to lists, and push manga to temp
            chapter_obj = {"id":chapter["id"], "volume":chapter['attributes']['volume'],
             "chapter":chapter['attributes']['chapter'],"title":chapter['attributes']['title']}
            if chapter_obj["volume"] is None:
                chapter_obj["volume"] = "Unspecified"
            if chapter_obj["title"] is None:
                chapter_obj["title"] = "Chapter "+chapter_obj["chapter"]
            
            

            for r in chapter['relationships']:
                if r['type'] == "manga":
                    if 'en' in r['attributes']['title']:
                        chapter_obj["manga"] = r['attributes']['title']['en']
                    elif 'altTitles' in r['attributes']:
                        chapter_obj["manga"] = ""
                        for item in r['attributes']['altTitles']:
                            if 'en' in item:
                                chapter_obj["manga"] = item['en']
                                break
                        if chapter_obj["manga"] == "":
                            chapter_obj["manga"] = "No English Title"
                    else:
                        chapter_obj["manga"] = "No English Title"
                elif r['type'] == "scanlation_group":
                    chapter_obj["group"] = r['attributes']['name']
            if 'group' not in chapter_obj:
                chapter_obj["group"] = "No Group"
            tempfeed.append(chapter_obj)
    #if last chapter wasn't found, get more from feed.
    if broken is False and list['firstRun'] is False:
        more_messages = await getListChapters(list, offset+limit)
        messages.append(more_messages)


    #if temp list is not empty
    if tempfeed is not None:
        tempfeed.reverse()
        for chap in tempfeed:
            #build messages and store
            message = "**{0}**\n".format(chap["manga"])
            message += "Volume {0} Chapter {1}\n".format(chap["volume"], chap["chapter"])
            message += "Title: {0} Group: {1}\n".format(chap["title"], chap["group"])
            message += "https://mangadex.org/chapter/{0}".format(chap["id"])
            messages.append(message)
            #push chapter to memory
            list['chapterCache'].insert(0,chap["id"])
        #trim memory
        del list['chapterCache'][10:]

    if list['firstRun'] == True:
        list['firstRun'] = False
    
    await update_list(list)

    #return message strings
    return messages


async def loadData():
#load username/password so they persist across sessions
    if os.path.isfile('userdata.json'):
        with open('userdata.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            config.stored_username = data['username']
            config.stored_password = data['password']
            config.token = data['token']
            temp_time = data['last_updated']
            config.last_updated = datetime.fromtimestamp(temp_time)
    

async def storeData():
    if config.isAuthed is True:
        data = {"username":config.stored_username, "password":config.stored_password, "token":config.token, "last_updated":config.last_updated.timestamp()}
        with open('userdata.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
#store username/password/last cached chapter ID so they persist across sessions

async def loadSubscription():
    if os.path.isfile('subscription.json'):
        with open('subscription.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            config.firstRun = data['firstRun']
            guild_id = data['guild']
            config.guild = bot.get_guild(guild_id)
            channel_id = data['channel']
            config.channel = bot.get_channel(channel_id)
            config.chapterCache = data['chapterCache']
            role_id = data['role']
            config.role = config.guild.get_role(role_id)
            config.subscription_active = data['subscription_active']
            if 'ignoredUploaders' in data:
                config.ignoredGroups = data['ignoredGroups']
            else:
                config.ignoredGroups = []
            if 'ignoredUploaders' in data:
                config.ignoredUploaders = data['ignoredUploaders']
            else:
                config.ignoredUploaders = []
            
            if 'subscribedLists' in data:
                await deserializeList(data['subscribedLists'])
            else:
                config.subscribedLists = []

            print('subscription loaded')
            if subscriptionLoop.is_running():
                subscriptionLoop.restart()
            else:
                await subscriptionLoop.start()


async def storeSubscription():

    #if config.subscription_active is True:
    data = {"guild":config.guild.id, "channel":config.channel.id, "role":config.role.id, 
    "subscription_active": config.subscription_active, "chapterCache":config.chapterCache, "firstRun": config.firstRun,
    "ignoredGroups":config.ignoredGroups, "ignoredUploaders":config.ignoredUploaders, "subscribedLists": await serializeLists()}
    with open('subscription.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    

async def serializeLists():
    listjson = []
    for x in config.subscribedLists:
        listjson.append({"guid": x['guid'], "guild": x['guild'].id, "channel": x['channel'].id, "role": x['role'].id, "firstRun": x['firstRun'], "subscription_active": x['subscription_active'], "chapterCache": x['chapterCache'] })
    return listjson

async def deserializeList(obj):
    config.subscribedLists = []
    for x in obj:
        guild = bot.get_guild(x['guild'])
        await add_list(x['guid'], guild, bot.get_channel(x['channel']), guild.get_role(x['role']), x['subscription_active'], x['firstRun'], x['chapterCache'])

async def reAuth():
    time.sleep(300)

    return try_auth(config.stored_username, config.stored_password)
    


async def validateTokens():
    try:
        if config.last_updated is None:
            return False

        if (datetime.now() - config.last_updated).total_seconds() < 890:
            return True
        
        check = await apiCall("/auth/check")
        if check['isAuthenticated']:
            #global token = check.token
            return True
        
        #print(config.token)

        refresh = await apiCall("/auth/refresh", method="POST", payload={"token":config.token['refresh']})
        #print(refresh)
        if refresh['result'] == "ok":
            config.token = refresh['token']
            config.last_updated = datetime.now()
            return True
        else:
            config.token = None
            status = await reAuth()
            if status == "Error":
                return False
            else:
                return True

        return False 
    except Exception as e:
        #print(str(e))
        #print("Error validating tokens")
        return False


async def apiCall(endpoint, method = "GET", payload = {}):
    try:
        if endpoint is None:
            return {"Error":"No endpoint"}
        if endpoint[0] != '/':
            endpoint = '/'+endpoint
        baseurl = 'https://api.mangadex.org'
        headers = {}
        #print('blah')
        if config.token is not None:
            #print('blah')
            #print('blah 2')
            headers["Authorization"] = "bearer " + config.token['session']
            #print('blah 3')
        if method == "GET":
            req = requests.get(baseurl+endpoint, params = payload, headers = headers)
        elif method == "POST":
            req = requests.post(baseurl+endpoint, json = payload, headers = headers)
        else:
            return {"Error":"Bad method"}
        
        if req.status_code > 200:
            if req.status_code == 401:
                #print(req.json())
                return {"Error":"Bad Auth"}
            else:
                #print("Error: {0}".format(req.json()))
                return {"Error":"Code "+str(req.status_code)}
            

        try: 
            return req.json()
        except:
            return {"Error":"Bad JSON"}
    except Exception as e:
        #print(str(e))
        return {"Error":"Uncaught Error: "+str(e)}

    
if os.path.isfile('secret.json'):
        with open('secret.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            config.secret = data['token']


bot.run(config.secret)
