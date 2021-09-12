import discord
import os.path
from discord.ext import tasks
from discord.ext import commands
import requests
from datetime import datetime
import config
import json
import time
bot = commands.Bot(command_prefix='$')

#globals
#config.firstRun = True
#config.isAuthed = []
#config.chapterCache = []
#config.maxCache = 30
#guild = []
#config.channel = []
#config.role = []
#config.token = []
#config.subscription_active = False
#config.stored_username = []
#config.stored_password = []
#config.last_updated = []
#client = discord.Client()

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
async def unsubscribe(ctx, temp=None):
    #config.guild = None
    #config.channel = None
    #config.role = None
    config.firstRun = True
    config.subscription_active = False
    #config.chapterCache = []
    #print('unsubscribed')
    await storeSubscription()
    subscriptionLoop.stop()
    await ctx.send("Successfully unsubscribed")

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
    payload = {"limit":limit, "translatedLanguage[]":"en", "offset":offset,"order[publishAt]":"desc","includes[]":["manga","scanlation_group"]}
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
    manga = {}
    manga_ids = []
    scanlation_groups = {}
    scan_group_ids = []
    messages = []
    #print("starting chapter loop")
    #print(chapters)
    for chapter in chapters:
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
                    #manga_ids.append(r['id'])
                    chapter_obj["manga"] = r['attributes']['title']['en']
                elif r['type'] == "scanlation_group":
                    #scan_group_ids.append(r['id'])
                    chapter_obj["group"] = r['attributes']['name']
            if 'group' not in chapter_obj:
                chapter_obj["group"] = "No Group"
            tempfeed.append(chapter_obj)
    #if last chapter wasn't found, get more from feed.
    if broken is False and config.firstRun is False:
        messages = getFeedChapters(offset+limit)

    ##not implemented

    #if temp list is not empty
    if tempfeed is not None:
        #get group names
        #uniqueGroups = list(set(scan_group_ids))
        #groupPayload = {"limit": len(uniqueGroups), "ids[]": uniqueGroups}
        #groupData = await apiCall("/group","GET", groupPayload)
       # if groupData['Error'] is not None:
       #if 'Error' not in groupData:
        #    for group in groupData['results']:
        #        scanlation_groups[group['data']['id']] = group['data']['attributes']['name']
        #scanlation_groups["No Group"] = 'No Group'
        #get manga names
        #uniqueManga = list(set(manga_ids))
        #mangaPayload = {"limit": len(uniqueManga), "ids[]": uniqueManga, "contentRating[]":["safe","suggestive","erotica","pornographic"]}
        #mangaData = await apiCall("/manga","GET", mangaPayload)
        #if mangaData['Error'] is not None:
        #if 'Error' not in mangaData:
        #    for mang in mangaData['results']:
        #        manga[mang['data']['id']] = mang['data']['attributes']['title']['en']
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
    
    await storeSubscription()

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
            print('subscription loaded')
            if subscriptionLoop.is_running():
                subscriptionLoop.restart()
            else:
                await subscriptionLoop.start()


async def storeSubscription():
    #if config.subscription_active is True:
    data = {"guild":config.guild.id, "channel":config.channel.id, "role":config.role.id, 
    "subscription_active": config.subscription_active, "chapterCache":config.chapterCache, "firstRun": config.firstRun}
    with open('subscription.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    

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
