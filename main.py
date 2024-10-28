import os, random, json, time, threading
from twitchio.ext import commands
from config.secrets import TWITCH_TOKEN, CLIENT_ID, CLIENT_SECRET, CHANNELS

os.system('cls')

# users not to show in chat
BLACKLIST = ['FILL THIS']

# what your points symbol is
POINTS = 'FILL THIS'

# time variables
HOUR, HALF_HOUR, QUARTER_HOUR = 3600, 1800, 900
DAY = HOUR * 24

# lottery and rewards
HUNDRED = 100
THOUSAND = 1000
MILLION = 1000000
LOTTERY_REWARD = 5 * THOUSAND 

# chat data path
DATA_PATH = 'chat_data.json'

# default json structure, for first launch and new users
DEFAULT_CHAT_DATA = {
    'user': {},
    'bot': {
        'count': 0,
        'timers': {}
    }
}
DEFAULT_USER_DATA = {
        'points': 100,
        'admin': False,
        'last_chatted': 1728911210.0784192,
        'discord': False,
        'stats': {'STR':10,'DEX':10,'CON':10,'INT':10,'WIS':10,'CHA':10},
        'timers': {}
}

class BOT(commands.Bot):
    def __init__(self):
        super().__init__(token=TWITCH_TOKEN, client_id = CLIENT_ID, client_secret = CLIENT_SECRET, prefix='!', initial_channels = CHANNELS)
        self.chat_data = self.load()
        self.force_lottery = False
        self.first = False

    def load(self):
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, 'r') as f:
                return json.load(f)
        return DEFAULT_CHAT_DATA
    
    def save(self):
        with open(DATA_PATH, 'w') as f:
            json.dump(self.chat_data, f)

    def user_cooldown(self, user, command_name, time_in_seconds):
        current_time = time.time()
        if command_name not in self.chat_data['users'][user]['timers']:
            self.chat_data['users'][user]['timers'][command_name] = current_time
            self.save()
            return True
        
        last_time = self.chat_data['users'][user]['timers'][command_name]
        if current_time - last_time > time_in_seconds:
            self.chat_data['users'][user]['timers'][command_name] = current_time
            self.save()
            return True
        return False
    
    def chat_cooldown(self, command_name, time_in_seconds):
        current_time = time.time()
        if command_name not in self.chat_data['timers']:
            self.chat_data['timers'][command_name] = current_time
            self.save()
            return True
        
        last_time = self.chat_data['timers'][command_name]
        if current_time - last_time > time_in_seconds:
            self.chat_data['timers'][command_name] = current_time
            self.save()
            return True
        return False
    
    def verify_user(func):
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            user = ctx.author.name
            if user not in self.chat_data['users']:
                await ctx.send(f'{user}, create a save using !new')
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    
    def get_active(self):
        current_time = time.time()
        active_users = []
        for user in self.chat_data['users']:
            if 'last_chatted' in self.chat_data['users'][user]:
                if current_time - self.chat_data['users'][user]['last_chatted'] < HOUR:
                    active_users.append(user)
        return active_users if active_users else None
    
    def reward_all(self, amt):
        for user in self.get_active():
            self.chat_data['users'][user]['points'] += amt
        self.save()

    def do_lottery(self):
        self.chat_data = self.load()
        if self.chat_data['users'] and self.chat_cooldown('lottery', HOUR) or self.force_lottery:
            self.force_lottery = False
            winner = random.choice(list(self.get_active())) if self.get_active() is not None else None
            if winner is None:
                return
            self.chat_data['users'][winner]['points'] += LOTTERY_REWARD
            self.save()
            print(f'Lottery: {winner} won {LOTTERY_REWARD}{POINTS}!')
    
    def delete_marked_users(self):
        for user in self.chat_data['users']:
            if 'delete' in self.chat_data['users'][user] and self.chat_data['users']['delete'] > HOUR:
                del self.chat_data['users'][user]
            self.save()

    def check_timers(self):
        self.do_lottery()
        self.delete_marked_users()
        threading.Timer(5, self.check_timers).start()

    def reset_timers(self):
        current_time = time.time()
        for timer in self.chat_data['timers']:
            self.chat_data['timers'][timer] = current_time
    
    def clean_username(self, username):
        return username[1:].lower() if username.startswith('@') else username.lower()
    
    def roll_stats(self):
        stats = {'STR':random.randint(1,18),'DEX':random.randint(1,18),'CON':random.randint(1,18),'INT':random.randint(1,18),'WIS':random.randint(1,18),'CHA':random.randint(1,18)}
        return stats

    def get_modifier(self, stat_value):
        return (stat_value - 10) // 2 if stat_value % 2 == 0 else (stat_value - 9) // 2
    
    async def event_ready(self):
        print(f'Login Successful!')

        self.reset_timers()
        self.save()
        self.check_timers()

    async def event_message(self, message):
        if not message.author or message.echo:
            return

        current_time = time.time()
        user = message.author.name
        self.chat_data = self.load()

        # Update user data
        if user in self.chat_data['users']:
            self.chat_data['users'][user]['last_chatted'] = current_time
            self.chat_data['users'][user]['points'] += 1
            self.save()

        # Get the color of the user if available (you might need to set this up)
        color = message.author.color if message.author.color else "#FFFFFF"  # Default to white if no color is provided

        # Append chat message to chat in chat_data.json with timestamps and color
        if user not in BLACKLIST and user in self.get_active():
            chat_entry = {
                'user': user,
                'message': message.content,
                'timestamp': current_time,
                'color': color
            }

            # Append the chat entry to the chat list
            self.chat_data['chat'].append(chat_entry)

            # Keep only the last 50 messages
            if len(self.chat_data['chat']) > 50:
                self.chat_data['chat'] = self.chat_data['chat'][-50:]

            # Save the updated chat data
            self.save()

        await self.handle_commands(message)

    async def can_afford(self, ctx: commands.Context, user: str, amt: int):
        if int(amt) > int(self.chat_data['users'][user]['points']):
            await ctx.send(f'{user}, you can\'t afford that!')
            return False
        return True

    # help
    @commands.command(name='help')
    @verify_user
    async def help(self, ctx: commands.Context):
        user = ctx.author.name
        if self.user_cooldown(user, 'help', QUARTER_HOUR):
            commands_list = [
                '!new ',
                '!delete ',
                '!bread ',
                '!hydrate ',
                '!stretch ',
                '!count ',
                '!challenge ',
                '!lottery ',
                '!coinflip ',
                '!gift ',
                '!quickticket '
            ]
            await ctx.send(f'Available commands: ' + ' '.join(commands_list))

    # new
    @commands.command(name='new')
    async def new(self, ctx: commands.Context):
        user = ctx.author.name
        if user not in self.chat_data['users']:
            self.chat_data['users'][user] = DEFAULT_USER_DATA
            await ctx.send(f'Generated a new save for: {user}!')
            self.save()

    # bread
    @commands.command(name='bread')
    @verify_user
    async def bread(self, ctx: commands.Context, target: str = None):
        if target is None:
            target = ctx.author.name

        target = self.clean_username(target)

        if target not in self.chat_data['users']:
            await ctx.send(f'Could not find {target}')
            return

        await ctx.send(f'{target} has: {self.chat_data['users'][target]['points']}{POINTS}')

    # delete
    @commands.command(name='delete')
    @verify_user
    async def delete(self, ctx: commands.Context):
        user = ctx.author.name
        if 'delete' in self.chat_data['users'][user]['timers']:
            return
        
        current_time = time.time()

        if user in self.chat_data['users']:
            await ctx.send(f'{user}, your data will be deleted in an hour. To cancel this, use !canceldelete')
            self.chat_data['users'][user]['timers']['delete'] = current_time

    # canceldelete
    @commands.command(name='canceldelete')
    @verify_user
    async def cancel_delete(self, ctx: commands.Context):
        user = ctx.command.name
        if 'delete' in self.chat_data['users'][user]:
            del self.chat_data['users'][user]['delete']
            await ctx.send(f'{user}, your data is safe from deletion.')

        # count
    @commands.command(name='count')
    @verify_user
    async def count(self, ctx: commands.Context, guessed_number = None):
        self.chat_data['count'] = int(self.chat_data['count'])
        if not guessed_number:
            await ctx.send(f'The next number in the count is {self.chat_data['count']}')
            return
        user = ctx.author.name
        if int(guessed_number) == int(self.chat_data['count']):
            self.reward_all(self.chat_data['count'])
            self.chat_data['count'] += 1
        else:
            self.chat_data['count'] = 1
            await ctx.send(f'{user} messed it all up! Restarting at {self.chat_data['count']}.')
        self.save()

    # discord
    @commands.command(name='discord')
    @verify_user
    async def discord(self, ctx: commands.Context):
        user = ctx.author.name
        if await self.can_afford(ctx,user, MILLION):
            await ctx.send(f'{user}, your request is being reviewed! Sit tight!')
            print(f'{user} has requested the discord link!')
            self.chat_data['users'][user]['discord'] = True
            self.chat_data['users'][user]['points'] -= MILLION
        self.save()

    # hydrate
    @commands.command(name='hydrate')
    @verify_user
    async def hydrate(self, ctx: commands.Context):
        price = 100
        user = ctx.author.name
        if not self.chat_cooldown('hydrate', HOUR):
            await ctx.send(f'Toast recently hydrated, but thanks for checking, {user}!')
            return
        self.chat_data['users'][user]['points'] -= price
        await ctx.send(f'{user} used {price} {POINTS} to remind Toast to hydrate!')
        self.save()

    # stretch
    @commands.command(name='stretch')
    @verify_user
    async def stretch(self, ctx: commands.Context):
        price = HUNDRED
        user = ctx.author.name
        if not self.chat_cooldown('stretch', HOUR):
            await ctx.send(f'Toast recently stretched, but thanks for checking, {user}!')
            return
        self.chat_data['users'][user]['points'] -= price
        await ctx.send(f'{user} used {price} {POINTS} to remind Toast to stretch!')
        self.save()
    
    # force lottery
    @commands.command(name='forcelottery')
    @verify_user
    async def forcelottery(self, ctx: commands.Context):
        user = ctx.author.name
        if self.chat_data['users'][user]['admin']:
            self.force_lottery = True
            self.do_lottery() 

    # lottery
    @commands.command(name='lottery')
    @verify_user
    async def lottery(self, ctx: commands.Context):
        current_time = time.time()
        last_time = self.chat_data['timers']['lottery']
        time_until_next_lotto = HOUR - (current_time - last_time)

        if time_until_next_lotto < 60:
            await ctx.send(f'{int(time_until_next_lotto)} seconds left!')
        else:
            minutes = int(time_until_next_lotto // 60)
            await ctx.send(f'{minutes} minutes left!')

    # quick ticket
    @commands.command(name='quickticket')
    @verify_user
    async def quickticket(self, ctx: commands.Context, tickets: int = None):
        price = HUNDRED
        user = ctx.author.name
        try:
            tickets = int(tickets)
        except:
            await ctx.send(f'Tickets must be an interger')

        if tickets is None or tickets <= 0:
            await ctx.send(f"!quickticket <amt of tickets> (each ticket costs 100{POINTS})")
            return

        value = tickets * price

        if await self.can_afford(ctx, user, value):
            self.chat_data['users'][user]['points'] -= value

            rewards = [random.randint(0,100),random.randint(100, 200), random.randint(200, 500), random.randint(500, 10000)]
            weights = [1000, 800, 199, 1] 
            total_winnings = 0

            for _ in range(tickets):
                reward = random.choices(rewards, weights=weights, k=1)[0]
                total_winnings += reward

            self.chat_data['users'][user]['points'] += total_winnings

            net_result = total_winnings - value
            if net_result >= 0:
                result_message = f"Gain: {net_result}{POINTS}"
            else:
                result_message = f"Loss: {abs(net_result)}{POINTS}"

            await ctx.send(f"{user} bought {tickets} {f'a quickticket' if tickets < 1 else f'quicktickets'} and won {total_winnings}{POINTS}! {result_message}")
        self.save()

    #coinflip
    @commands.command(name='coinflip')
    @verify_user
    async def coinflip(self, ctx: commands.Context, amt: int = None, choice: str = 'heads'):
        user = ctx.author.name
        amt = int(amt)
        if amt is None:
            await ctx.send(f'{user}, usage: !coinflip <amount> <heads/tails>')
            return

        if not await self.can_afford(ctx, user, amt):
            return

        flip_result = random.choice(['heads', 'tails'])

        if flip_result == choice.lower():
            self.chat_data['users'][user]['points'] += amt
            result = 'win'
        else:
            self.chat_data['users'][user]['points'] -= amt
            result = 'lose'

        await ctx.send(f'{user} bet {choice} for {amt} {POINTS} and it landed on {flip_result}. They {result}!')
        self.save()

    # gift
    @commands.command(name='gift')
    @verify_user
    async def gift(self, ctx: commands.Context, target: str, amt: int):
        user = ctx.author.name
        target = self.clean_username(target)
        amt = int(amt)

        if target not in self.chat_data['users']:
            await ctx.send(f'{target} has not registered using !new.')
            return
        if 'admin' not in self.chat_data['users'][user]:
            if not await self.can_afford(ctx, user, amt):  # Pass context and use await
                return
            if user == target:
                await ctx.send(f'{user}, you cannot send yourself a gift')
                return

            self.chat_data['users'][user]['points'] -= amt
        self.chat_data['users'][target]['points'] += amt
        self.save()
        choice = random.choice(['gift','package','bag','box','basket'])
        await ctx.send(f'{user} sent {target} a {choice} of {amt} {POINTS}.')

    @commands.command(name='d')
    @verify_user
    async def d(self, ctx:commands.Context, dice_size : int = None, amt : int = 1):
        user = ctx.author.name
        dice_size = int(dice_size)
        dice = [4,6,8,12,20,100]
        if dice_size not in dice:
            await ctx.send(f'Available dice: {dice}')
            return
        
        result = random.randint(1,dice_size)
        await ctx.send(f'{user} rolled a {dice_size} sided die and it landed on {result}')

    @commands.command(name='reroll')
    @verify_user
    async def reroll(self, ctx: commands.Context):
        user = ctx.author.name
        cooldown = HOUR * 24 
        if self.user_cooldown(user,'reroll', cooldown):
            self.chat_data['users'][user]['stats'] = self.roll_stats()
            await ctx.send(f'{user} rerolled their stats! {self.chat_data['users'][user]['stats']}')
            self.save()
            return

    @commands.command(name='stats')
    @verify_user
    async def stats(self, ctx: commands.Context):
        user = ctx.author.name
        await ctx.send(f'{user} stats: {self.chat_data['users'][user]['stats']}')

    # attack
    @commands.command(name='fight')
    @verify_user
    async def fight(self, ctx: commands.Context, target):
        user = ctx.author.name
        target = self.clean_username(target)
        if not self.user_cooldown(user,'fight',15):
            return

        if target not in self.chat_data['users']:
            await ctx.send(f'Could not find {target}')
            return
        
        if user == target:
            await ctx.send(f'{user}, you can\'t attack yourself?!')
            return
        
        if target == 'theonewhotookyourtoast':
            await ctx.send(f'What makes you think you could fight a bear?')
            return
        
        if target not in self.get_active():
            await ctx.send(f'Trying to attack someone who isn\'t active? Really?')
            return

        choice = random.choice(list(self.chat_data['users'][user]['stats']))

        user_roll = random.randint(0,20) + self.get_modifier(self.chat_data['users'][user]['stats'][choice])
        target_roll = random.randint(0,20) + self.get_modifier(self.chat_data['users'][target]['stats'][choice])

        winner = user if user_roll > target_roll else target
        loser = target if winner == user else user
        min_points = min(100, self.chat_data['users'][loser]['points'])
        self.chat_data['users'][winner]['points'] += min_points
        self.chat_data['users'][loser]['points'] -= min_points

        result = 'won' if winner == user else 'lost'
        await ctx.send(f'{user} challenged {target} to a game of {choice} and {result} {min_points}{POINTS}!')
        self.save()

    # first
    @commands.command(name='first')
    @verify_user
    async def first(self, ctx: commands.Context):
        if not self.first:
            self.first = not self.first
            user = ctx.author.name
            await ctx.send(f'{user} was here first! Here\'s 1000🍞!~')
            self.chat_data['users'][user]['points'] += 1000
            self.save()
            return
        await ctx.send(f'Sorry! Someone else claimed it before you!')

    # lurk
    @commands.command(name='lurk')
    @verify_user
    async def lurk(self, ctx: commands.Context):
        user = ctx.author.name
        await ctx.send(f'I think {user} came in.. must be lurking around here somewhere...')

    # lurk
    @commands.command(name='join')
    @verify_user
    async def join(self, ctx: commands.Context):
        user = ctx.author.name
        await ctx.send(f'{user} joined the game!')


if __name__ == '__main__':
    bot = BOT()
    bot.run()
    
exit()