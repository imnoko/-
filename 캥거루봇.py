import discord
from discord.ext import commands
from collections import deque
from discord import app_commands
import asyncio
from typing import Dict
from datetime import timedelta
from discord.ui import Button, View
import os
import psutil
import sys
import json

ALLOWED_USER_ID = 1286302274829680676

intents = discord.Intents.default()
intents = discord.Intents.all()
intents.members = True  # 서버 멤버 관련 이벤트를 처리하려면 이 인텐트를 활성화해야 합니다.
intents.message_content = True  # 메시지 내용을 읽어야 한다면 이 인텐트를 활성화해야 합니다.

client = discord.Client(intents=intents)

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


server_settings = {}  # 서버 설정 데이터
SETTINGS_FILE = "server_settings.json"

# 설정 데이터 로드 및 저장
def load_settings():
    global server_settings
    try:
        with open(SETTINGS_FILE, "r") as file:
            server_settings = json.load(file)
    except FileNotFoundError:
        server_settings = {}

def save_settings():
    with open(SETTINGS_FILE, "w") as file:
        json.dump(server_settings, file, indent=4)

class RoleButtonView(View):
    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role

    @discord.ui.button(label="역할 받기", style=discord.ButtonStyle.primary)
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 버튼 클릭한 유저에게 역할을 부여
        await interaction.user.add_roles(self.role)

        embed = discord.Embed(
            title="역할 부여 성공",
            description=f"축하합니다! {self.role.name} 역할을 받았습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

load_settings()

@bot.event
async def on_ready():
    print(f"✅ {bot.user}으로 로그인했습니다!")
    synced = await bot.tree.sync()
    server_count = len(bot.guilds)
    saver_count = server_count
    await bot.change_presence(
        status=discord.Status.idle,  # 온라인 상태 (초록색)
        activity=discord.Activity(
            type=discord.ActivityType.streaming,  # 방송 중 상태
            name=f"{saver_count}개 서버에서 관리(현재 추가된 서버)"
        )
    )



class CloseTicketButton(discord.ui.View):
    def __init__(self, channel, user):
        super().__init__()
        self.channel = channel
        self.user = user

    @discord.ui.button(label="티켓 닫기", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("이 티켓을 닫을 권한이 없습니다.", ephemeral=True)
            return

        await self.channel.set_permissions(self.user, read_messages=False, send_messages=False)
        await interaction.response.send_message("티켓이 닫혔습니다. 이 채널은 아카이브 처리됩니다.")
        await self.channel.edit(name=f"닫힌-{self.channel.name}")

class TicketCategoryDropdown(discord.ui.Select):
    def __init__(self, categories, interaction):
        options = [
            discord.SelectOption(label=category, description=f"{category}에 대한 티켓을 생성합니다.")
            for category in categories
        ]
        super().__init__(placeholder="티켓 카테고리를 선택하세요.", min_values=1, max_values=1, options=options)
        self.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        category_name = self.values[0]
        guild = self.interaction.guild

        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            category = await guild.create_category(category_name)

        ticket_channel_name = f"{category_name}-{self.interaction.user.name}-{self.interaction.user.discriminator}"
        ticket_channel = await guild.create_text_channel(ticket_channel_name, category=category)

        await ticket_channel.set_permissions(self.interaction.user, read_messages=True, send_messages=True)
        await ticket_channel.set_permissions(guild.default_role, read_messages=False)

        embed = discord.Embed(
            title="🎟️ 티켓 채널",
            description="문의가 접수되었습니다. 아래 버튼을 눌러 티켓을 닫을 수 있습니다.",
            color=discord.Color.green()
        )

        await ticket_channel.send(
            embed=embed, view=CloseTicketButton(ticket_channel, self.interaction.user)
        )

        await interaction.response.send_message(
            f"티켓 채널이 생성되었습니다! {ticket_channel.mention}", ephemeral=True
        )

class TicketCategoryView(discord.ui.View):
    def __init__(self, categories, interaction):
        super().__init__()
        self.add_item(TicketCategoryDropdown(categories, interaction))

@tree.command(name="도움말", description="봇의 명령어에 대한 도움말을 확인합니다.")
async def help_command(interaction: discord.Interaction):
    # 서포트 서버 링크 버튼 만들기
    support_button = Button(label="서포트 서버", style=discord.ButtonStyle.link, url="https://discord.gg/EynyexWpmc")

    # Embed 메시지 작성
    embed = discord.Embed(
        title="캥거루봇 도움말",
        description="캥거루봇에서 사용할 수 있는 명령어 목록",
        color=discord.Color.yellow()
    )

    # 각 명령어를 필드로 추가
    embed.add_field(name="/동기화", value="봇의 명령어를 이 서버에 동기화합니다.", inline=False)
    embed.add_field(name="/상태", value="봇의 실행 서버의 상태를 점검합니다.", inline=False)
    embed.add_field(name="/슬로우모드", value="해당 채널에 슬로우 모드를 설정합니다.", inline=False)
    embed.add_field(name="/역할전체지급", value="해당 서버의 모든 유저에게 역할을 지급합니다.", inline=False)
    embed.add_field(name="/역할전체회수", value="해당 서버의 모든 유저의 역할을 회수합니다.", inline=False)
    embed.add_field(name="/역할지급", value="지정한 유저에게 역할을 지급합니다.", inline=False)
    embed.add_field(name="/역할회수", value="지정한 유저의 역할을 회수합니다.", inline=False)
    embed.add_field(name="/유저차단", value="지정한 유저를 서버에서 차단합니다.", inline=False)
    embed.add_field(name="/유저채금", value="지정한 유저를 서버에서 타임아웃합니다.", inline=False)
    embed.add_field(name="/유저추방", value="지정한 유저를 서버에서 추방합니다.", inline=False)
    embed.add_field(name="/인증버튼", value="지정한 역할을 받는 인증버튼을 생성합니다.", inline=False)
    embed.add_field(name="/청소", value="채팅에서 지정된 숫자만큼 메세지를 삭제합니다.", inline=False)
    embed.add_field(name="/초대링크", value="캥거루봇의 초대링크를 제공합니다.", inline=False)
    embed.add_field(name="/티켓생성", value="티켓 생성을 위한 메세지를 전송합니다.", inline=False)
    embed.add_field(name="/핑", value="봇의 실행 서버의 핑을 확인합니다.", inline=False)

    # 버튼을 위한 뷰 생성
    view = View()
    view.add_item(support_button)

    # Embed 메시지 전송
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="동기화", description="봇의 명령어를 이 서버에 동기화합니다.")
async def sync_commands(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
        try:
            await tree.sync(guild=interaction.guild)  # 특정 서버에 동기화
            await interaction.response.send_message("명령어가 이 서버에 동기화되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"동기화 중 오류가 발생했습니다: {e}", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ 관리자만 이 명령어를 사용할 수 있습니다.", ephemeral=True)

@tree.command(name="핑", description="봇의 실행 서버의 핑을 확인합니다.")
async def 핑(interaction: discord.Interaction):
    # 봇의 핑 측정
    latency = bot.latency * 1000  # latency는 초 단위로 제공되므로, 밀리초로 변환
    
    # EMBED 생성
    embed = discord.Embed(title="🏓 퐁", description=f"`{latency:.2f}ms`", color=discord.Color.blue())
    
    # 명령어를 실행한 유저에게 응답 보내기
    await interaction.response.send_message(embed=embed)


@tree.command(name="청소", description="채팅에서 지정된 숫자만큼 메시지를 삭제합니다.")
async def 청소(interaction: discord.Interaction, 숫자: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("이 명령어를 사용하려면 관리자 권한이 필요합니다.", ephemeral=True)
        return

    # 숫자가 1보다 작은 값이면, 에러 메시지 반환
    if 숫자 < 1:
        await interaction.response.send_message("삭제할 메시지 수는 1 이상이어야 합니다.", ephemeral=True)
        return

    # 메시지 삭제 시 권한 확인
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("이 명령어를 사용하려면 메시지 관리 권한이 필요합니다.", ephemeral=True)
        return

    # 채널에서 지정된 숫자만큼 메시지 삭제
    deleted = await interaction.channel.purge(limit=숫자)
    await interaction.response.send_message(f"{len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)

@tree.command(name="상태", description="봇의 실행 서버의 상태를 점검합니다.")
async def 상태(interaction: discord.Interaction):
    # 서버 상태 점검 (예: CPU 사용량, 메모리 사용량 등)
    cpu_usage = psutil.cpu_percent()
    memory_info = psutil.virtual_memory()
    memory_usage = memory_info.percent

    # 서버 상태 판단
    if cpu_usage < 50 and memory_usage < 50:
        color = discord.Color.green()
    elif cpu_usage < 75 and memory_usage < 75:
        color = discord.Color.orange()
    else:
        color = discord.Color.red()

    # EMBED 생성
    embed = discord.Embed(title="서버 상태 점검", color=color)
    embed.add_field(name="CPU 사용량", value=f"`{cpu_usage}%`", inline=False)
    embed.add_field(name="메모리 사용량", value=f"`{memory_usage}%`", inline=False)
    
    # 명령어를 실행한 유저에게 응답 보내기
    await interaction.response.send_message(embed=embed)
    


@tree.command(name="인증버튼", description="지정한 역할을 받는 인증 버튼을 생성합니다.")
@app_commands.describe(role="역할을 부여할 역할")
async def authentication_button(interaction: discord.Interaction, role: discord.Role):
    # 관리자만 사용할 수 있도록 권한 제한
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 오류",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 인증 버튼을 생성할 뷰 객체 생성
    view = RoleButtonView(role)

    # Embed 메시지와 버튼을 해당 채널에 전송
    embed = discord.Embed(
        title="역할을 받으세요!",
        description="아래 버튼을 클릭하여 역할을 받으세요.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="역할지급", description="지정한 유저에게 역할을 지급합니다.")
@app_commands.describe(user="역할을 부여할 유저", role="부여할 역할")
async def assign_role(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    # 관리자만 사용할 수 있도록 권한 제한
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 오류",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 역할 부여
    try:
        await user.add_roles(role)
        embed = discord.Embed(
            title="역할 부여",
            description=f"{user.mention} 님에게 {role.name} 역할이 부여되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        embed = discord.Embed(
            title="권한 오류",
            description="역할을 부여할 권한이 없습니다. 권한을 확인해 주세요.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

@tree.command(name="역할회수", description="지정한 유저의 역할을 회수합니다.")
@app_commands.describe(user="역할을 회수할 유저", role="회수할 역할")
async def remove_role(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    # 관리자만 사용할 수 있도록 권한 제한
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 오류",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 역할 회수
    try:
        await user.remove_roles(role)
        embed = discord.Embed(
            title="역할 회수",
            description=f"{user.mention} 님에게서 {role.name} 역할이 회수되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        embed = discord.Embed(
            title="권한 오류",
            description="역할을 회수할 권한이 없습니다. 권한을 확인해 주세요.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="오류",
            description=f"역할을 회수하는 중 오류가 발생했습니다: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

@tree.command(name="역할전체회수", description="해당 서버의 모든 유저의 역할을 회수합니다.")
@app_commands.describe(role="회수할 역할")
async def remove_role_from_all(interaction: discord.Interaction, role: discord.Role):
    # 관리자만 사용할 수 있도록 권한 제한
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 오류",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 서버의 모든 멤버에게 역할 회수
    try:
        # 역할을 회수할 멤버 목록 가져오기
        members = interaction.guild.members
        for member in members:
            # 자신에게 역할을 회수할 수 있을 경우에만
            if not member.bot and role in member.roles:  # 봇에게는 역할을 회수하지 않음
                await member.remove_roles(role)
        
        embed = discord.Embed(
            title="역할 전체 회수 완료",
            description=f"서버의 모든 유저에게서 {role.name} 역할이 회수되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        embed = discord.Embed(
            title="권한 오류",
            description="역할을 회수할 권한이 없습니다. 권한을 확인해 주세요.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="오류",
            description=f"역할을 회수하는 중 오류가 발생했습니다: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

@tree.command(name="역할전체지급", description="해당 서버의 모든 유저에게 역할을 지급합니다.")
@app_commands.describe(role="부여할 역할")
async def assign_role_to_all(interaction: discord.Interaction, role: discord.Role):
    # 관리자만 사용할 수 있도록 권한 제한
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 오류",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 서버의 모든 멤버에게 역할 부여
    try:
        # 역할을 부여할 멤버 목록 가져오기
        members = interaction.guild.members
        for member in members:
            # 자신에게 역할을 부여할 수 있을 경우에만
            if not member.bot:  # 봇에게는 역할을 부여하지 않음
                await member.add_roles(role)
        
        embed = discord.Embed(
            title="역할 전체 부여 완료",
            description=f"서버의 모든 유저에게 {role.name} 역할이 부여되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        embed = discord.Embed(
            title="권한 오류",
            description="역할을 부여할 권한이 없습니다. 권한을 확인해 주세요.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="오류",
            description=f"역할을 부여하는 중 오류가 발생했습니다: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)


@tree.command(name="티켓생성", description="티켓 생성을 위한 메시지를 전송합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def create_ticket_command(interaction: discord.Interaction):
    categories = ["문의", "기타"]
    embed = discord.Embed(
        title="문의 티켓",
        description="원하시는 티켓 카테고리를 선택하세요.",
        color=discord.Color.blue()
    )
    view = TicketCategoryView(categories, interaction)
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="슬로우모드", description="해당 채널에 슬로우 모드를 설정합니다.")
@app_commands.describe(seconds="슬로우모드 시간 (초)", channel="슬로우모드를 설정할 채널")
async def slowmode(interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
    # 관리자만 사용할 수 있도록 권한 제한
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 오류",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 채널 설정 (명령어를 사용한 채널이 기본값)
    if channel is None:
        channel = interaction.channel

    # 슬로우모드 설정
    try:
        await channel.edit(slowmode_delay=seconds)
        embed = discord.Embed(
            title="슬로우모드 설정",
            description=f"{channel.mention} 채널의 슬로우모드가 {seconds}초로 설정되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        embed = discord.Embed(
            title="권한 오류",
            description="슬로우모드를 설정할 권한이 없습니다. 권한을 확인해 주세요.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)



@tree.command(name="유저채금", description="지정한 유저를 서버에서 타임아웃합니다.")
@app_commands.describe(user="타임아웃 시킬 유저", duration="타임아웃 기간", unit="시간, 분, 초 단위")
async def timeout_user(interaction: discord.Interaction, user: discord.User, duration: int, unit: str):
    # 관리자만 사용할 수 있도록 권한 제한
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 오류",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 시간 단위 처리
    time_map = {
        "시": 3600,  # 1시간 = 3600초
        "분": 60,    # 1분 = 60초
        "초": 1      # 1초
    }

    if unit not in time_map:
        embed = discord.Embed(
            title="단위 오류",
            description="단위는 '시', '분', '초' 중 하나여야 합니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    timeout_duration = timedelta(seconds=duration * time_map[unit])

    try:
        # 타임아웃 적용
        await user.timeout(timeout_duration)
        embed = discord.Embed(
            title="타임아웃 적용",
            description=f"{user.mention} 님이 {duration}{unit} 동안 타임아웃 되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        embed = discord.Embed(
            title="권한 오류",
            description="타임아웃을 적용할 수 없습니다. 권한을 확인해 주세요.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

@tree.command(name="초대링크", description="봇의 초대 링크를 제공합니다.")
async def invite(interaction: discord.Interaction):
    bot_invite_url = f"https://discord.com/oauth2/authorize?client_id=1323658238499225650&permissions=8&integration_type=0&scope=bot"
    embed = discord.Embed(
        title="초대 링크",
        description=f"[여기를 클릭하여 봇을 초대하세요]({bot_invite_url})",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="유저추방", description="지정한 유저를 서버에서 추방합니다.")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "사유 없음"):
    # 관리자 권한 확인
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 부족",
            description="이 명령어를 사용할 권한이 없습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # 추방 처리
    try:
        await user.kick(reason=reason)
        embed = discord.Embed(
            title="유저 추방됨",
            description=f"**{user}** 님이 서버에서 추방되었습니다.\n사유: {reason}",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="오류 발생",
            description=f"유저를 추방할 수 없습니다.\n오류: {e}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
@tree.command(name="유저차단", description="지정한 유저를 서버에서 차단합니다.")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "사유 없음"):
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="권한 부족",
            description="이 명령어를 사용할 권한이 없습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    try:
        await user.ban(reason=reason)
        embed = discord.Embed(
            title="유저 차단됨",
            description=f"**{user}** 님이 서버에서 차단되었습니다.\n사유: {reason}",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="오류 발생",
            description=f"유저를 차단할 수 없습니다.\n오류: {e}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)



bot.run("MTMyMzY1ODIzODQ5OTIyNTY1MA.GajuNj.o4Z2XrrtvE2coALdaWpSxRD1FhO3uCOr6WQEyA")