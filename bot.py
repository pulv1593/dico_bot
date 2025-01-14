import discord
import os
import re
# import yt_dlp as youtube_dl
from yt_dlp import YoutubeDL 
import asyncio
from discord.ext import commands
#from dico_token import Token #로컬 기능 테스트 시 사용.
from collections import defaultdict, deque

#배포환경에서 사용되는 봇 토큰
TOKEN = os.getenv("DISCORD_TOKEN")
 
# bot intents 정의
intents = discord.Intents.default()
intents.message_content = True

# bot 기본 세팅, 명령어 앞에 !로 시작하게 설정.
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("/"),
    description='디스코드 입장을 위한 테스트 코드',
    intents=intents,
)

# 서버별 대기열 저장
queues = defaultdict(deque)

# 명령어 실행 상태를 저장할 플래그
command_in_progress = {}

#봇 이벤트 처리 함수 모음 
@bot.event
async def on_ready():
    print('{0.user} 봇을 실행합니다.'.format(bot))
 
# 명령어 함수 모음
# 노래봇을 음성채팅에 데려오는 명령어
@bot.command(aliases=['입장'])
async def join(ctx):
    embed = discord.Embed(title = "디스코드 봇 도우미(개발용)", description = "음성 채널 개발용 디스코드 봇",color=0x00ff56)
    channel = ctx.author.voice.channel
    
    if ctx.author.voice is None:
        embed.add_field(name=':exclamation:', value="음성 채널에 유저가 존재하지 않습니다. 1명 이상 입장해주세요.")
        await ctx.send(embed=embed)
        raise commands.CommandInvokeError("사용자가 존재하는 음성 채널을 찾지 못했습니다.")
    
    if ctx.voice_client is not None:
        embed.add_field(name=":robot:",value="사용자가 있는 채널로 이동합니다.", inline=False)
        await ctx.send(embed=embed)
        print("음성 채널 정보: {0.author.voice}".format(ctx))
        print("음성 채널 이름: {0.author.voice.channel}".format(ctx))
        return await ctx.voice_client.move_to(channel)
        
    await channel.connect()

#노래봇을 음성채널에서 내보내는 명령어 
@bot.command(aliases=['나가기'])
async def out(ctx):
    try:
        embed = discord.Embed(color=0x00ff56)
        embed.add_field(name=":regional_indicator_b::regional_indicator_y::regional_indicator_e:",value=" {0.author.voice.channel}에서 내보냈습니다.".format(ctx),inline=False)
        await bot.voice_clients[0].disconnect()
        await ctx.send(embed=embed)
    except IndexError as error_message:
        print(f"에러 발생: {error_message}")
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":grey_question:",value="{0.author.voice.channel}에 유저가 존재하지 않거나 봇이 존재하지 않습니다.\\n다시 입장후 퇴장시켜주세요.".format(ctx),inline=False)
        await ctx.send(embed=embed)
    except AttributeError as not_found_channel:
        print(f"에러 발생: {not_found_channel}")
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":x:",value="봇이 존재하는 채널을 찾는 데 실패했습니다.")
        await ctx.send(embed=embed)

# /play 명령어 내장 함수 모음
# 1. URL 유효성 검사 함수
def is_valid_url(url):
    regex = r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+|https?://(?:www\.)?youtu\.be/[\w-]+)'
    return re.match(regex, url) is not None

# 2. 노래 검색 함수(키워드 입력시에만 동작.)
async def search_song(ctx, search):
    ytdl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch',
        'duration': '<600',  # 10분 이하 동영상만 검색
        'source_address': '0.0.0.0',  # IPv4 연결 사용
    }
    ytdl = YoutubeDL(ytdl_opts)

    # 키워드가 입력된 경우 검색 수행
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, lambda : ytdl.extract_info(f"ytsearch3:{search}", download=False))
    entries = info.get('entries', [])

    return entries

# 3. 대기열에 노래 추가 함수
def add_to_queue(ctx, song):
    queues[ctx.guild.id].append(song)
    
# 4. 노래 재생 함수
async def play_next_song(ctx):
    if len(queues[ctx.guild.id]) > 0:  # 대기열에 노래가 남아있으면
        next_song = queues[ctx.guild.id].popleft()  # 대기열에서 첫 번째 곡을 꺼냄
        url = next_song['url']
        title = next_song['title']

        embed = discord.Embed(title=":musical_note: 다음 곡 재생", description=f"**{title}**", color=0x1DB954)
        await ctx.send(embed=embed)

        # FFMPEG 옵션 설정
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -loglevel quiet',
            'options': '-vn',
        }

        audio_source = discord.FFmpegOpusAudio(url, **FFMPEG_OPTIONS)
        ctx.voice_client.play(
            audio_source,
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop).result()
        )
    else:
        # 대기열이 비었을 때 대기 상태로 전환
        embed = discord.Embed(title=":zzz: 대기열이 비었습니다", description="새 노래를 추가하지 않으면 5분 후에 음성 채널에서 나갑니다.", color=0xFFA500)
        await ctx.send(embed=embed)

        # 5분 대기 후 음성 채널에서 나가기
        await asyncio.sleep(300)  # 300초 = 5분
        if not ctx.voice_client.is_playing() and len(queues[ctx.guild.id]) == 0:
            await ctx.voice_client.disconnect()

# 5. 재생 상태 점검 함수
async def ensure_playing(ctx):
    while ctx.voice_client and ctx.voice_client.is_connected():
        await asyncio.sleep(1)  # 1초마다 상태를 확인

# 노래 재생 명령어
@bot.command(aliases=['재생'])
async def p(ctx, *, search: str):
    global command_in_progress
    
    # 현재 서버에서 명령어가 실행 중인지 확인
    if command_in_progress.get(ctx.guild.id, False):
        await ctx.send("이미 노래를 검색 중입니다. 검색이 완료된 후 다시 시도해주세요.")
        return
    
    # 플래그 설정: 명령어 실행 중
    command_in_progress[ctx.guild.id] = True
    
    try:
        #활성화된 음성채널에 없을 시
        if ctx.author.voice is None:
            await ctx.send("음성 채널에 입장한 후 명령어를 사용해주세요.")
            return
        #노래봇이 음성채널에 들어가있지 않은 경우
        if ctx.voice_client is None:
            await ctx.invoke(bot.get_command('join'))

        #url로 입력한 경우 처리
        if is_valid_url(search):
            try:
                ytdl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                }
                ytdl = YoutubeDL(ytdl_opts)
                info = ytdl.extract_info(search, download=False)
                url = info.get('url')
                title = info.get('title', '알 수 없는 제목')

                # 대기열에 추가
                add_to_queue(ctx, {'url': url, 'title': title})
        
                # 대기열에 추가된 곡 표시
                embed = discord.Embed(title=":musical_note: 대기열 추가", description=f"**{title}**", color=0x1DB954)
                await ctx.send(embed=embed)

                # 노래 재생
                if not ctx.voice_client.is_playing():
                    await play_next_song(ctx)
                else:
                    await ctx.send("노래가 이미 재생 중입니다. 대기열에 추가되었습니다.")
                    return
            except Exception as e:
                await ctx.send("URL에서 음악을 가져올 수 없습니다. 링크를 확인해주세요.")
                print(f"에러 발생: {e}")
            finally:
                # 플래그 해제: 명령어 종료
                command_in_progress[ctx.guild.id] = False
                return
        
        # 키워드 검색인 경우
        # "검색 중입니다!" 메시지 보내기
        loading_message = await ctx.send("🔍 노래를 찾고있어요..! 조금만 기다려주세요...")
        try:
            # 노래 검색
            entries = await search_song(ctx, search)
            #검색 결과가 없는 경우
            if not entries:
                await loading_message.edit(content="검색 결과가 없습니다. 다른 키워드로 시도해주세요.")
                return

            # 검색결과를 discord 메세지로 출력
            embed = discord.Embed(title="검색 결과", description="원하는 곡 번호를 입력해주세요!\n '0'을 입력하면 취소됩니다.", color=0x1DB954)
            for i, entry in enumerate(entries[:3]):  # 최대 3개 출력
                embed.add_field(
                    name=f"{i+1}. {entry['title']}", 
                    value="\u200b",  # 빈 줄 표시
                    inline=False
                )

            # 기존 메시지 수정
            await loading_message.edit(content=None, embed=embed)

            # 사용자 입력 대기
            def check(msg):
                return msg.author == ctx.author and msg.content.isdigit() and 0 <= int(msg.content) <= len(entries[:3])
            
            #60초간 사용자 입력 대기
            try:
                msg = await bot.wait_for('message', check=check, timeout=60.0)
                selection = int(msg.content)

                if selection == 0:
                    await ctx.send("노래 검색이 취소되었습니다.")
                    # 플래그 해제: 명령어 종료
                    command_in_progress[ctx.guild.id] = False
                    return
            
                selected_entry = entries[selection - 1]

                # 선택된 음원 재생
                url = selected_entry.get('url') or selected_entry.get('webpage_url')
                title = selected_entry.get('title', '알 수 없는 제목')

                # 대기열에 추가
                add_to_queue(ctx, {'url': url, 'title': title})

                embed = discord.Embed(title=":musical_note: 대기열에 추가되었습니다!", description=f"**{title}**", color=0x1DB954)
                await ctx.send(embed=embed)

                # 오디오 재생
                if not ctx.voice_client.is_playing():
                    await play_next_song(ctx)
                else:
                    # 현재 대기열 출력
                    embed = discord.Embed(title="현재 대기열", color=0x1DB954)
                    for i, song in enumerate(queues[ctx.guild.id]):
                        embed.add_field(name=f"{i+1}. {song['title']}", value="\u200b", inline=False)
                    await ctx.send(embed=embed)  
            except asyncio.TimeoutError:
                await ctx.send("시간 초과로 명령어가 취소되었습니다.")
                return
        except Exception as e:
            await ctx.send("검색을 실패했습니다.")
            print(f"에러 발생: {e}")
    except Exception as e:
            await ctx.send("음악을 재생할 수 없습니다. 링크 또는 키워드를 확인해주세요.")
            print(f"에러 발생: {e}")
    finally:
        # 플래그 해제: 명령어 종료
        command_in_progress[ctx.guild.id] = False

#노래 재생을 끝내고 내보내기
@bot.command(aliases=['멈춤', '정지'])
async def stop(ctx):
    if ctx.voice_client is None:
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":x:", value="봇이 음성 채널에 연결되어 있지 않습니다.")
        await ctx.send(embed=embed)
        return
    else:
        # 음악이 재생 중이면 멈추기
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        # 음성 채널에서 봇을 나가게 함
        await ctx.voice_client.disconnect()
        
        embed = discord.Embed(color=0x00ff56)
        embed.add_field(name=":stop_button:", value="음악을 멈추고 음성 채널에서 나갔습니다.", inline=False)
        await ctx.send(embed=embed)
        return
 
# 대기열 확인 명령어
@bot.command(aliases=['대기열'])
async def queue(ctx):
    if ctx.guild.id not in queues or len(queues[ctx.guild.id]) == 0:
        await ctx.send("현재 대기열에 노래가 없습니다.")
        return

    # 대기열이 있을 경우 출력
    embed = discord.Embed(title="현재 대기열", color=0x1DB954)
    for i, song in enumerate(queues[ctx.guild.id]):
        embed.add_field(name=f"{i+1}. {song['title']}", value="\u200b", inline=False)

    await ctx.send(embed=embed)

# 재생중인 노래 스킵 명령어
@bot.command(aliases=['스킵'])
async def skip(ctx):
    if ctx.voice_client is None:
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":x:", value="봇이 음성 채널에 연결되어 있지 않습니다.")
        await ctx.send(embed=embed)
        return

    if not ctx.voice_client.is_playing():
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":x:", value="현재 재생 중인 음악이 없습니다.")
        await ctx.send(embed=embed)
        return
    
    # 대기열에 다음 곡이 있는지 확인
    if len(queues[ctx.guild.id]) == 0:
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":x:", value="대기열에 다음 곡이 없습니다. stop 명령어를 이용해주세요.")
        await ctx.send(embed=embed)
        return

    # 현재 곡을 멈추고 다음 곡 재생
    ctx.voice_client.stop()
    embed = discord.Embed(color=0x1DB954)
    embed.add_field(name=":fast_forward:", value="현재 곡을 스킵하고 다음 곡을 재생합니다.", inline=False)
    await ctx.send(embed=embed)

    # 약간의 지연 후 다음 곡 재생
    await asyncio.sleep(1)  # 1초 지연을 추가
    if not ctx.voice_client.is_playing():  # 중복 재생 방지
        await play_next_song(ctx)
    
@bot.command(aliases=['다시재생'])
async def rep(ctx):
    if ctx.voice_client.stop():
        await play_next_song(ctx)
    else:
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name="?x?", value="이미 재생중입니다.")
        await ctx.send(embed=embed)
        return
    
#bot.run(Token) #local에서 테스트 할때 쓰는 토큰
bot.run(TOKEN) #배포시 사용될 봇 토큰