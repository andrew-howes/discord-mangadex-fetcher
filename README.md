# discord-mangadex-fetcher

Needs a discord bot account. 

change secret_copy.json to secret.json, and add your token there.

Commands: 
  $auth: Uses username/password as positional arguments. Use your mangadex credentials to auth. 
    Will delete the message that calls it so your information doesn't stay public
  $subscribe: Use with a channel name and a role to mention. Will mention that role when publishing
    new chapters. 
  $unsubscribe: Turns off subscription
  $subscription status: displays subscription status.
  
  Subscription has a 6 minute refresh rate, and gets from /user/follows/manga/feed. Will look up manga and group names, doesn't show the uploader at the moment.
  
