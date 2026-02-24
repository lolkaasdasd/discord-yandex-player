import os
import re
import io
import time
import json
import asyncio
import textwrap
import random
import math
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp
from yandex_music import Client
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Загрузка токенов
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
YANDEX_TOKEN = os.getenv('YANDEX_TOKEN')

# Настройки yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(CURRENT_DIR, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
BLACKLIST_FILE = os.path.join(CURRENT_DIR, 'blacklist.json')

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

guild_states = {}

try:
    ym_client = Client(YANDEX_TOKEN).init()
    print(f"🌌 Яндекс Музыка: Эфир настроен на {ym_client.account_status().account.first_name}")
except Exception as e:
    print(f"❌ Ошибка подключения к Яндексу: {e}")

def get_state(guild_id):
    if guild_id not in guild_states:
        guild_states[guild_id] = {
            'queue': [],           
            'vibe_active': False,  
            'vc': None,            
            'current_track_info': None, 
            'chill_mode': False,
            'last_msg': None,
            'track_start_time': 0
        }
    return guild_states[guild_id]

COLOR_ERROR = 0xff003c   
DEFAULT_COLOR = 0xb148d2

# --- ОБРАБОТЧИК ОШИБОК (ЧИСТИМ ЛОГИ) ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass # Забаненный чел - сообщение уже отправлено
    elif isinstance(error, commands.CommandNotFound):
        pass # Кто-то ввел левую команду или смайлик
    else:
        print(f"[{time.strftime('%H:%M:%S')}] ОШИБКА: {error}")

# --- ЛОКАЛЬНЫЙ ЧЕРНЫЙ СПИСОК И ГЕНЕРАЦИЯ КАРТОЧКИ БАНА ---
def load_blacklist():
    if not os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, 'w') as f: 
            json.dump([], f)
    try:
        with open(BLACKLIST_FILE, 'r') as f: 
            return json.load(f)
    except: 
        return []

def get_banned_image():
    for ext in ['gif', 'png', 'jpg', 'jpeg']:
        path = os.path.join(CURRENT_DIR, f"banned.{ext}")
        if os.path.exists(path):
            return path
    return None

def generate_banned_card(user_name):
    width, height = 800, 300
    bg_color = (43, 45, 49, 255) # Идеальный цвет фона Discord (#2b2d31)
    panel_color = (30, 31, 34, 255)

    snarky_texts = [
        "Создатель выдернул твой шнур.",
        "Отдыхай, бро. Твоя остановка.",
        "Терминал для тебя закрыт.",
        "Смотри, но руками не трогай.",
        "Нейросеть отклонила твой доступ.",
        "Путевка на банановые острова."
		"сосо малыха"
    ]
    text = random.choice(snarky_texts)

    img_path = get_banned_image()
    banned_frames = []
    
    if img_path:
        try:
            b_img = Image.open(img_path)
            if getattr(b_img, "is_animated", False):
                for i in range(b_img.n_frames):
                    b_img.seek(i)
                    banned_frames.append(b_img.convert("RGBA").resize((240, 240), Image.Resampling.LANCZOS))
            else:
                banned_frames.append(b_img.convert("RGBA").resize((240, 240), Image.Resampling.LANCZOS))
        except Exception: pass
    
    if not banned_frames:
        ph = Image.new('RGBA', (240, 240), (255, 60, 80, 255))
        ImageDraw.Draw(ph).text((40, 100), "BANNED", fill="white")
        banned_frames = [ph]

    # Если гифка огромная, берем первые 40 кадров
    if len(banned_frames) > 40:
        banned_frames = banned_frames[:40]

    frame_count = len(banned_frames) if len(banned_frames) > 1 else 30
    frames = []

    try:
        font_title = ImageFont.truetype(os.path.join(CURRENT_DIR, "font_regular.ttf"), 38)
        font_desc = ImageFont.truetype(os.path.join(CURRENT_DIR, "font_italic.ttf"), 24)
    except:
        font_title = font_desc = ImageFont.load_default()

    for i in range(frame_count):
        canvas = Image.new('RGBA', (width, height), bg_color)
        
        # 3D Тень под главную плашку
        shadow = Image.new('RGBA', (width, height), (0,0,0,0))
        ImageDraw.Draw(shadow).rounded_rectangle((35, 35, width-25, height-25), radius=20, fill=(0,0,0,120))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        canvas.paste(shadow, (0,0), shadow)
        
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((30, 30, width-40, height-40), radius=20, fill=panel_color)
        
        # Текст
        draw.text((60, 60), "ДОСТУП ЗАКРЫТ", font=font_title, fill=(255, 60, 80, 255))
        wrapped_desc = textwrap.fill(f"{user_name}, {text}", width=23)
        draw.text((60, 120), wrapped_desc, font=font_desc, fill=(200, 200, 200, 255))
        draw.text((60, height - 80), "Music Protection", font=font_desc, fill=(88, 101, 242, 255))

        # Анимация: если это одно фото, оно плавно левитирует вверх-вниз
        b_frame = banned_frames[i % len(banned_frames)]
        y_offset = int(math.sin(i / frame_count * math.pi * 2) * 12) if len(banned_frames) == 1 else 0
        
        mask = Image.new("L", (240, 240), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 240, 240), radius=25, fill=255)
        
        canvas.paste(b_frame, (width - 300, 30 + y_offset), mask)
        frames.append(canvas.convert("RGB"))

    buffer = io.BytesIO()
    frames[0].save(buffer, format='GIF', save_all=True, append_images=frames[1:], duration=60, loop=0)
    buffer.seek(0)
    return buffer.getvalue()

async def send_banned_message(target, user):
    try:
        gif_bytes = await bot.loop.run_in_executor(None, generate_banned_card, user.display_name)
        file = discord.File(fp=io.BytesIO(gif_bytes), filename="banned_card.gif")
        
        embed = discord.Embed(color=COLOR_ERROR)
        embed.set_image(url="attachment://banned_card.gif")
        
        if isinstance(target, discord.Interaction):
            await target.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await target.send(embed=embed, file=file, delete_after=15)
    except discord.NotFound:
        pass # Защита от спама в консоль

def is_not_blacklisted():
    async def predicate(ctx):
        banned_ids = load_blacklist()
        if str(ctx.author.id) in banned_ids or ctx.author.id in banned_ids:
            await send_banned_message(ctx, ctx.author)
            return False
        return True
    return commands.check(predicate)

# --- ПРОВЕРКА НА НАХОЖДЕНИЕ В ТОМ ЖЕ ГОЛОСОВОМ КАНАЛЕ ---
def in_same_voice_channel():
    async def predicate(ctx):
        state = get_state(ctx.guild.id)
        bot_vc = state['vc']
        
        if not bot_vc or not bot_vc.is_connected(): return True
            
        if not ctx.author.voice or ctx.author.voice.channel != bot_vc.channel:
            embed = discord.Embed(
                title="🎧 Ошибка доступа", 
                description=f"{ctx.author.mention}, ты должен находиться в одном голосовом канале с ботом, чтобы переключать музыку!", 
                color=COLOR_ERROR
            )
            await ctx.send(embed=embed, delete_after=7)
            return False
            
        return True
    return commands.check(predicate)

# --- КАРАОКЕ (ПАРСЕР LRC ТАЙМКОДОВ) ---
async def karaoke_task(interaction, track_id, state):
    try:
        def get_sync():
            try:
                # Запрашиваем текст именно в формате LRC (с таймкодами)
                t_lyrics = ym_client.tracks_lyrics(track_id, 'LRC')
                if not t_lyrics: return None
                
                lrc_text = t_lyrics.fetch_lyrics() # Скачиваем файл текста
                
                class SyncLine:
                    def __init__(self, offset_ms, line):
                        self.offset_ms = offset_ms
                        self.line = line
                        
                lines = []
                # Парсим LRC файл (например: [00:15.54] Слова песни)
                for line_str in lrc_text.split('\n'):
                    tags = re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', line_str)
                    if tags:
                        txt = re.sub(r'\[\d+:\d+(?:\.\d+)?\]', '', line_str).strip()
                        for t in tags:
                            m, s = int(t[0]), float(t[1])
                            lines.append(SyncLine(int((m * 60 + s) * 1000), txt))
                
                lines.sort(key=lambda x: x.offset_ms)
                return lines if lines else None
            except Exception as e:
                print(f"ОШИБКА КАРАОКЕ: {e}")
                return None

        lines = await bot.loop.run_in_executor(None, get_sync)
        if not lines:
            return await interaction.followup.send("❌ Для этого трека синхронный текст еще не завезли в базу Яндекса.", ephemeral=True)

        msg = await interaction.followup.send("🎤 **Настраиваю микрофон...**", ephemeral=True, wait=True)
        
        last_idx = -1
        last_edit_time = 0
        
        while state['vc'] and state['vc'].is_playing() and state['current_track_info'] and state['current_track_info'].get('track_id') == track_id:
            current_time_ms = (time.time() - state['track_start_time']) * 1000
            
            curr_idx = -1
            for i, line in enumerate(lines):
                if line.offset_ms <= current_time_ms: 
                    curr_idx = i
                else: 
                    break
                    
            if curr_idx != last_idx and (time.time() - last_edit_time > 1.5):
                text = ""
                start_i = max(0, curr_idx - 2)
                end_i = min(len(lines), curr_idx + 3)
                
                for i in range(start_i, end_i):
                    if i == curr_idx: 
                        text += f"🟢 **{lines[i].line}**\n"
                    else: 
                        text += f"*{lines[i].line}*\n"
                        
                try:
                    await msg.edit(embed=discord.Embed(title="🎤 Караоке Эфир", description=text, color=0x30d760))
                    last_idx = curr_idx
                    last_edit_time = time.time()
                except discord.HTTPException: pass 
                
            await asyncio.sleep(0.5)
            
        try: await msg.edit(embed=discord.Embed(title="🎤 Караоке завершено", description="Трек закончился.", color=0x2b2d31))
        except: pass

    except Exception as e: 
        print(f"Ошибка караоке: {e}")

# --- ВИЗУАЛ: ПАНЕЛЬ КНОПОК --- #
class PlayerControls(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        banned_ids = load_blacklist()
        if str(interaction.user.id) in banned_ids or interaction.user.id in banned_ids:
            await send_banned_message(interaction, interaction.user)
            return False
            
        state = get_state(self.ctx.guild.id)
        bot_vc = state['vc']
        
        if bot_vc and bot_vc.is_connected():
            if not interaction.user.voice or interaction.user.voice.channel != bot_vc.channel:
                embed = discord.Embed(
                    title="🎧 Ошибка", 
                    description=f"{interaction.user.mention}, ты должен находиться в голосовом канале с ботом, чтобы нажимать эти кнопки!", 
                    color=COLOR_ERROR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return False
                
        return True

    @discord.ui.button(label="Пауза/Плей", style=discord.ButtonStyle.primary, emoji="⏯️", row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try: await interaction.response.defer()
        except discord.NotFound: return
        await self.ctx.invoke(self.ctx.bot.get_command('pause'))

    @discord.ui.button(label="Скип", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try: await interaction.response.defer()
        except discord.NotFound: return
        await self.ctx.invoke(self.ctx.bot.get_command('skip'))

    @discord.ui.button(label="Стоп", style=discord.ButtonStyle.danger, emoji="🛑", row=0)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try: await interaction.response.defer()
        except discord.NotFound: return
        await self.ctx.invoke(self.ctx.bot.get_command('stop'))

    @discord.ui.button(label="Караоке", style=discord.ButtonStyle.secondary, emoji="🎤", row=1)
    async def karaoke_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try: await interaction.response.defer(ephemeral=True)
        except discord.NotFound: return
        state = get_state(self.ctx.guild.id)
        info = state.get('current_track_info')
        if not info or not info.get('track_id'):
            return await interaction.followup.send("Для этого трека функция недоступна.", ephemeral=True)
        bot.loop.create_task(karaoke_task(interaction, info['track_id'], state))

    @discord.ui.button(label="Моя Волна", style=discord.ButtonStyle.success, emoji="🌊", row=1)
    async def wave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try: await interaction.response.defer()
        except discord.NotFound: return
        await self.ctx.invoke(self.ctx.bot.get_command('wave'))

    @discord.ui.button(label="В избранное", style=discord.ButtonStyle.success, emoji="💖", row=1)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.ctx.guild.id)
        info = state.get('current_track_info')
        if not info:
            return await interaction.response.send_message("Сейчас ничего не играет.", ephemeral=True)
            
        try:
            embed = discord.Embed(title="💖 Сохраненный трек", description=f"**{info['title']}**", color=info['color'])
            if info.get('cover_url'): 
                embed.set_thumbnail(url=info['cover_url'])
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("Трек успешно отправлен тебе в ЛС! 💌", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ У тебя закрыты личные сообщения!", ephemeral=True)

# --- ХЕЛПЕРЫ ДЛЯ ЯНДЕКСА --- #
def get_ffmpeg_opts(chill_mode=False):
    opts = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
    filters = ["afade=t=in:ss=0:d=2"] 
    
    if chill_mode:
        filters.append("bass=g=6:f=110:w=0.6,volume=0.4")
        
    opts['options'] = f'-vn -af "{",".join(filters)}"'
    return opts

async def async_ym_search(query):
    def search():
        res = ym_client.search(query, type_='track')
        if res.tracks: return res.tracks.results[0]
        return None
    return await bot.loop.run_in_executor(None, search)

async def async_ym_direct_link(track_id):
    def get_link():
        track = ym_client.tracks([track_id])[0]
        info = track.get_download_info(get_direct_links=True)
        best = sorted(info, key=lambda x: x.bitrate_in_kbps, reverse=True)[0]
        title = f"{track.artists[0].name} - {track.title}" if track.artists else track.title
        cover = f"https://{track.cover_uri.replace('%%', '400x400')}" if track.cover_uri else None
        return best.direct_link, title, cover, track.id
    return await bot.loop.run_in_executor(None, get_link)

async def get_spotify_title(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html = await response.text()
                match = re.search(r'<title>(.*?)</title>', html)
                if match: return match.group(1).split('- song and lyrics')[0].split('|')[0].strip()
    except: pass
    return None

async def extract_ytdl_info(url):
    data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    return data['url'], data.get('title', 'Неизвестный трек'), data.get('thumbnail'), None

# --- ГЕНЕРАЦИЯ АНИМИРОВАННОЙ GIF-КАРТОЧКИ ТРЕКА --- #
def generate_animated_vibe_card(image_bytes, title, is_wave=False):
    try:
        cover = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    except:
        cover = Image.new('RGBA', (400, 400), (40, 40, 40, 255))

    resample_method = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
    small = cover.resize((1, 1), resample=resample_method)
    dom_color = small.getpixel((0, 0))

    width, height = 800, 300
    canvas = Image.new('RGBA', (width, height), dom_color)
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 160))
    canvas = Image.alpha_composite(canvas, overlay)

    try:
        font_title = ImageFont.truetype(os.path.join(CURRENT_DIR, "font_regular.ttf"), 42)
        font_eq = ImageFont.truetype(os.path.join(CURRENT_DIR, "font_regular.ttf"), 20)
        font_status = ImageFont.truetype(os.path.join(CURRENT_DIR, "font_italic.ttf"), 22)
    except:
        try:
            font_title = ImageFont.truetype("arialbd.ttf", 42)
            font_status = ImageFont.truetype("ariali.ttf", 22)
            font_eq = ImageFont.truetype("arial.ttf", 20)
        except:
            font_title, font_status, font_eq = [ImageFont.load_default()] * 3

    artist_text = "Сейчас играет"
    track_text = title
    if " - " in title:
        parts = title.split(" - ", 1)
        artist_text, track_text = parts[0], parts[1]

    if is_wave: artist_text = f"Моя волна: {artist_text}"

    draw = ImageDraw.Draw(canvas)
    wrapped_title = textwrap.fill(track_text, width=20)
    
    draw.text((45, 70), artist_text.upper(), font=font_status, fill=(200, 220, 255, 255))
    draw.text((45, 110), wrapped_title, font=font_title, fill=(255, 255, 255, 255))
    draw.text((45, height - 60), "Made By Zaza", font=font_eq, fill=(30, 215, 96, 255))

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=35, fill=255)
    
    base_bg = Image.new("RGBA", (width, height), (57, 58, 65, 255))
    base_bg.paste(canvas, (0, 0), mask=mask)

    vinyl_size = 240
    vinyl = Image.new('RGBA', (vinyl_size, vinyl_size), (0,0,0,0))
    v_draw = ImageDraw.Draw(vinyl)
    
    v_draw.ellipse((0, 0, vinyl_size-1, vinyl_size-1), fill=(18, 18, 18, 255))
    
    for i in range(12, 60, 12):
        v_draw.ellipse((i, i, vinyl_size-i-1, vinyl_size-i-1), outline=(40, 40, 40, 255), width=1)
        
    inner_size = int(vinyl_size * 0.45)
    inner_cover = cover.resize((inner_size, inner_size), resample_method)
    c_mask = Image.new('L', (inner_size, inner_size), 0)
    ImageDraw.Draw(c_mask).ellipse((0, 0, inner_size-1, inner_size-1), fill=255) 
    
    offset = (vinyl_size - inner_size) // 2
    vinyl.paste(inner_cover, (offset, offset), c_mask)
    
    h_size = 14
    h_off = (vinyl_size - h_size) // 2
    v_draw.ellipse((h_off, h_off, h_off+h_size, h_off+h_size), fill=(25, 25, 25, 255)) 

    cover_x = width - vinyl_size - 40
    cover_y = (height - vinyl_size) // 2
    
    shadow_canvas = Image.new('RGBA', (vinyl_size + 60, vinyl_size + 60), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_canvas)
    shadow_draw.ellipse((30, 30, vinyl_size + 30, vinyl_size + 30), fill=(0, 0, 0, 200))
    shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(12))
    base_bg.paste(shadow_canvas, (cover_x - 15, cover_y - 15), shadow_canvas)

    frames = []
    for angle in range(0, 360, 15):
        frame = base_bg.copy()
        rotated_vinyl = vinyl.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=False)
        frame.paste(rotated_vinyl, (cover_x, cover_y), rotated_vinyl)
        frames.append(frame.convert("RGB"))

    buffer = io.BytesIO()
    frames[0].save(
        buffer, 
        format='GIF', 
        save_all=True, 
        append_images=frames[1:], 
        duration=50, 
        loop=0
    )
    buffer.seek(0)
    
    discord_color = discord.Color.from_rgb(dom_color[0], dom_color[1], dom_color[2])
    return buffer.getvalue(), discord_color

async def fetch_image_and_generate_card(url, title, is_wave=False):
    image_bytes = b""
    if url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
        except Exception: pass
    return await bot.loop.run_in_executor(None, generate_animated_vibe_card, image_bytes, title, is_wave)

# --- ЛОГИКА ВОСПРОИЗВЕДЕНИЯ --- #
def disable_old_buttons(state):
    if state.get('last_msg'):
        try:
            bot.loop.create_task(state['last_msg'].edit(view=None))
        except Exception: 
            pass

def play_next(ctx, error=None):
    if error: print(f"Ошибка воспроизведения: {error}")
    state = get_state(ctx.guild.id)
    vc = state['vc']

    if not vc or not vc.is_connected(): return

    coro = process_next_track(ctx)
    bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(coro))

async def send_playing_card(ctx):
    state = get_state(ctx.guild.id)
    info = state['current_track_info']
    
    disable_old_buttons(state)
    
    artist_name = "Неизвестный Исполнитель"
    if " - " in info['title']:
        artist_name = info['title'].split(" - ", 1)[0]
        
    avatar_url = info.get('cover_url') or bot.user.display_avatar.url
    webhook_name = f"🌊 {artist_name}" if info.get('is_wave') else artist_name
    webhook_name = webhook_name[:80] 

    file = discord.File(fp=io.BytesIO(info['card_bytes']), filename="vibe_card.gif")
    embed = discord.Embed(color=info['color'])
    embed.set_image(url="attachment://vibe_card.gif")
    
    footer = "🌙 Chill-режим (Мягкий басс)" if state['chill_mode'] else "🎵 Стандартное звучание"
    req_name = info['requester'].display_name if info.get('requester') else "Нейросеть Яндекса"
    embed.set_footer(text=f"Заказ от: {req_name} | {footer}")

    try:
        webhooks = await ctx.channel.webhooks()
        webhook = discord.utils.get(webhooks, name="MusicVibe_Zaza")
        if not webhook:
            webhook = await ctx.channel.create_webhook(name="MusicVibe_Zaza")
            
        msg = await webhook.send(
            username=webhook_name,
            avatar_url=avatar_url,
            embed=embed,
            file=file,
            view=PlayerControls(ctx),
            wait=True 
        )
        state['last_msg'] = msg
    except discord.Forbidden:
        msg = await ctx.send(embed=embed, file=file, view=PlayerControls(ctx))
        state['last_msg'] = msg
        
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=info['title']))

async def process_next_track(ctx):
    state = get_state(ctx.guild.id)
    vc = state['vc']

    if len(state['queue']) > 0:
        track = state['queue'].pop(0)
        
        card_bytes, d_color = await fetch_image_and_generate_card(track['cover'], track['title'], is_wave=False)
        
        state['current_track_info'] = {
            'title': track['title'],
            'cover_url': track['cover'], 
            'requester': track['requester'],
            'is_wave': False,
            'color': d_color,
            'card_bytes': card_bytes,
            'track_id': track.get('track_id')
        }
        
        await send_playing_card(ctx)
        
        state['track_start_time'] = time.time()
        ffmpeg_options = get_ffmpeg_opts(state['chill_mode'])
        vc.play(discord.FFmpegPCMAudio(track['url'], **ffmpeg_options), after=lambda e: play_next(ctx, e))

    elif state['vibe_active']:
        try:
            def get_vibe():
                station = ym_client.rotor_station_tracks('user:onyourwave')
                next_track = station.sequence[0].track
                ym_client.rotor_station_feedback('user:onyourwave', 'trackStarted', track_id=next_track.id)
                return next_track

            wave_track = await bot.loop.run_in_executor(None, get_vibe)
            url, title, cover, t_id = await async_ym_direct_link(wave_track.id)
            
            card_bytes, d_color = await fetch_image_and_generate_card(cover, title, is_wave=True)
            
            state['current_track_info'] = {
                'title': title,
                'cover_url': cover,
                'requester': None,
                'is_wave': True,
                'color': d_color,
                'card_bytes': card_bytes,
                'track_id': t_id
            }
            
            await send_playing_card(ctx)

            state['track_start_time'] = time.time()
            ffmpeg_options = get_ffmpeg_opts(state['chill_mode'])
            vc.play(discord.FFmpegPCMAudio(url, **ffmpeg_options), after=lambda e: play_next(ctx, e))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="❌ Сбой Волны", description=f"Эфир прерван: {e}", color=COLOR_ERROR))
            state['vibe_active'] = False
            state['current_track_info'] = None
            disable_old_buttons(state)
    else:
        disable_old_buttons(state)
        state['current_track_info'] = None
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Тишину | !help"))

# --- ИВЕНТЫ --- #
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return
    
    for guild_id, state in guild_states.items():
        vc = state.get('vc')
        if vc and vc.is_connected() and before.channel == vc.channel:
            members = [m for m in vc.channel.members if not m.bot]
            if len(members) == 0:
                await asyncio.sleep(30)
                if vc.is_connected() and len([m for m in vc.channel.members if not m.bot]) == 0:
                    disable_old_buttons(state)
                    await vc.disconnect()
                    state['vc'] = None
                    state['queue'] = []
                    state['vibe_active'] = False
                    state['current_track_info'] = None
                    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Тишину | !help"))

# --- КОМАНДЫ ДИСКОРДА --- #
@bot.command(name="help", aliases=["h", "помощь"])
@is_not_blacklisted()
async def help_command(ctx):
    embed = discord.Embed(title="🌌 Музыкальный Терминал", description="Добро пожаловать в панель управления.", color=DEFAULT_COLOR)
    embed.add_field(name="🎵 Управление", value="`!play <запрос>` — Включить трек\n`!pause` — Пауза/Плей\n`!skip` — Следующий трек\n`!stop` — Выключить музыку", inline=False)
    embed.add_field(name="✨ Атмосфера", value="`!wave` — Моя Волна (Авто-подбор)\n`!chill` — Фоновый басс", inline=False)
    embed.add_field(name="📋 Инфо", value="`!np` — Что сейчас играет\n`!q` — Очередь треков", inline=False)
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user.display_avatar else None)
    await ctx.send(embed=embed)

@bot.command(aliases=['np', 'now'])
@is_not_blacklisted()
async def nowplaying(ctx):
    state = get_state(ctx.guild.id)
    if not state['vc'] or not state['vc'].is_playing() and not state['vc'].is_paused():
        return await ctx.send(embed=discord.Embed(title="🔇 В эфире тишина", description="Сейчас ничего не играет.", color=0x2b2d31))
    
    if state['current_track_info']:
        await send_playing_card(ctx)

@bot.command()
@is_not_blacklisted()
@in_same_voice_channel()
async def join(ctx):
    if not ctx.author.voice:
        return await ctx.send(embed=discord.Embed(title="❌ Ошибка", description="Зайди в голосовой канал!", color=COLOR_ERROR), delete_after=10)
    
    channel = ctx.author.voice.channel
    state = get_state(ctx.guild.id)
    if ctx.voice_client: await ctx.voice_client.move_to(channel)
    else: state['vc'] = await channel.connect()

@bot.command(aliases=['p'])
@is_not_blacklisted()
@in_same_voice_channel()
async def play(ctx, *, query: str):
    if not ctx.voice_client: await ctx.invoke(join)
    state = get_state(ctx.guild.id)
    msg = await ctx.send(embed=discord.Embed(title="📡 Сканирую эфир...", description=f"Ищу: `{query}`", color=0xf1c40f))

    url_to_play = title = cover = t_id = None
    try:
        if "spotify.com" in query:
            spotify_title = await get_spotify_title(query)
            if not spotify_title: return await msg.edit(embed=discord.Embed(title="❌ Ошибка", description="Не удалось распознать ссылку Spotify.", color=COLOR_ERROR))
            ym_track = await async_ym_search(spotify_title)
            if ym_track: url_to_play, title, cover, t_id = await async_ym_direct_link(ym_track.id)
            else: return await msg.edit(embed=discord.Embed(title="❌ Ошибка", description="Трек не найден.", color=COLOR_ERROR))
        elif "music.yandex" in query and "track/" in query:
            track_id = query.split('track/')[-1].split('?')[0].split('/')[0]
            url_to_play, title, cover, t_id = await async_ym_direct_link(track_id)
        elif "http" in query:
            url_to_play, title, cover, t_id = await extract_ytdl_info(query)
        else:
            ym_track = await async_ym_search(query)
            if ym_track: url_to_play, title, cover, t_id = await async_ym_direct_link(ym_track.id)
            else: return await msg.edit(embed=discord.Embed(title="❌ Пусто", description="Ничего не найдено.", color=COLOR_ERROR))
    except Exception as e:
        return await msg.edit(embed=discord.Embed(title="❌ Сбой сети", description=str(e), color=COLOR_ERROR))

    state['queue'].append({'url': url_to_play, 'title': title, 'cover': cover, 'requester': ctx.author, 'track_id': t_id})
    await msg.delete()
    
    await ctx.send(embed=discord.Embed(title="📥 Трек в очереди", description=f"**{title}**", color=DEFAULT_COLOR), delete_after=15)
    if not state['vc'].is_playing() and not state['vc'].is_paused(): await process_next_track(ctx)

@bot.command()
@is_not_blacklisted()
@in_same_voice_channel()
async def pause(ctx):
    state = get_state(ctx.guild.id)
    if state['vc']:
        if state['vc'].is_playing(): 
            state['vc'].pause()
            await ctx.send(embed=discord.Embed(title="⏸️ Эфир приостановлен", color=0xf1c40f), delete_after=5)
        elif state['vc'].is_paused(): 
            state['vc'].resume()
            await ctx.send(embed=discord.Embed(title="▶️ Эфир возобновлен", color=0x30d760), delete_after=5)

@bot.command()
@is_not_blacklisted()
@in_same_voice_channel()
async def chill(ctx):
    state = get_state(ctx.guild.id)
    state['chill_mode'] = not state['chill_mode']
    if state['chill_mode']: 
        await ctx.send(embed=discord.Embed(title="🌙 Chill режим", description="Фоновый басс включен.", color=0x111122), delete_after=10)
    else: 
        await ctx.send(embed=discord.Embed(title="🔊 Возврат к стандарту", description="Эквалайзер отключен.", color=DEFAULT_COLOR), delete_after=10)

@bot.command()
@is_not_blacklisted()
@in_same_voice_channel()
async def wave(ctx):
    if not ctx.voice_client: await ctx.invoke(join)
    state = get_state(ctx.guild.id)
    state['vibe_active'] = not state['vibe_active']
    
    if state['vibe_active']:
        await ctx.send(embed=discord.Embed(title="🌊 Погружение в Мою Волну", description="Нейросеть взяла управление.", color=0x00f0ff))
        if not state['vc'].is_playing(): await process_next_track(ctx)
    else: 
        await ctx.send(embed=discord.Embed(title="🛑 Волна остановлена", color=COLOR_ERROR))

@bot.command()
@is_not_blacklisted()
@in_same_voice_channel()
async def skip(ctx):
    state = get_state(ctx.guild.id)
    if state['vc'] and (state['vc'].is_playing() or state['vc'].is_paused()):
        state['vc'].stop()
        await ctx.send(embed=discord.Embed(title="⏭️ Скип...", color=0x3498db), delete_after=5)

@bot.command(aliases=['q'])
@is_not_blacklisted()
async def queue(ctx):
    state = get_state(ctx.guild.id)
    if not state['queue']: return await ctx.send(embed=discord.Embed(title="Очередь пуста 🪹", color=0x2b2d31))
    
    q_list = ""
    for i, t in enumerate(state['queue']):
        if i >= 10:
            q_list += f"\n*...и еще {len(state['queue']) - 10} треков*"
            break
        req = t.get('requester').display_name if t.get('requester') else "Неизвестно"
        q_list += f"`{i+1}.` **{t['title']}** *(от {req})*\n"
    await ctx.send(embed=discord.Embed(title=f"📋 Плейлист ожидания", description=q_list, color=DEFAULT_COLOR))

@bot.command()
@is_not_blacklisted()
@in_same_voice_channel()
async def stop(ctx):
    state = get_state(ctx.guild.id)
    disable_old_buttons(state)
    state['queue'], state['vibe_active'] = [], False
    if state['vc']: 
        await state['vc'].disconnect()
        state['vc'] = None
    await ctx.send(embed=discord.Embed(title="🔌 Отключение", description="Эфир прерван.", color=COLOR_ERROR))
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Тишину | !help"))

bot.run(DISCORD_TOKEN)