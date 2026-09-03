"""Pulse Discord Bot -- Phase 12: Discord Integration.

This bot:
  1. Listens for messages in a designated channel or DM
  2. Forwards questions to POST /qa (RAG pipeline)
  3. Creates issues via POST /issues
  4. Delivers personalized notifications via DM
  5. Shows team status, escalation queue, etc.

Run with: python -m bot.pulse_bot
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

import discord
from discord.ext import commands, tasks

from bot.config import config

logger = logging.getLogger("pulse_bot")

# ─── Bot Setup ────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(
    command_prefix=config.COMMAND_PREFIX,
    intents=intents,
    description=f"{config.BOT_NAME} -- Hackathon Concierge Bot",
)


# ─── HTTP Helper ──────────────────────────────────────────


async def api_request(
    method: str,
    path: str,
    json_data: dict | None = None,
    params: dict | None = None,
) -> dict | list | str:
    """Make an HTTP request to the backend API."""
    import aiohttp

    url = f"{config.BACKEND_URL}{path}"
    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json_data, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                text = await resp.text()
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
    except Exception as e:
        logger.error("API request failed: %s %s -> %s", method, path, e)
        return {"error": str(e)}


# ─── Event Handlers ───────────────────────────────────────


@bot.event
async def on_ready():
    """Bot startup."""
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    logger.info("Backend URL: %s", config.BACKEND_URL)
    logger.info("Channel ID: %s", config.DISCORD_CHANNEL_ID)

    # Start notification delivery loop
    if not notification_loop.is_running():
        notification_loop.start()

    # Set bot status
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name=f"{config.COMMAND_PREFIX}help | Hackathon Concierge",
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)


@bot.event
async def on_message(message: discord.Message):
    """Handle incoming messages."""
    # Ignore own messages
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)

    # If in the designated channel (not a command), treat as a question
    if (
        message.channel.id == config.DISCORD_CHANNEL_ID
        and not message.content.startswith(config.COMMAND_PREFIX)
        and not message.author.bot
    ):
        await handle_channel_message(message)

    # DM handling
    if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
        await handle_dm(message)


# ─── Message Handlers ─────────────────────────────────────


async def handle_channel_message(message: discord.Message):
    """Handle a message in the designated channel -- forward to Q&A."""
    question = message.content.strip()
    if not question:
        return

    # Show typing indicator
    async with message.channel.typing():
        # Forward to Q&A endpoint
        result = await api_request("POST", "/qa", json_data={"question": question})

        if isinstance(result, dict) and "answer" in result:
            answer = result["answer"]
            sources = result.get("sources", [])
            confidence = result.get("confidence", 0.0)

            # Build response embed
            embed = discord.Embed(
                title="Question Answered",
                description=answer[:2000],
                color=config.COLOR_SUCCESS if confidence > 0.5 else config.COLOR_WARNING,
            )
            embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)

            if sources:
                source_text = "\n".join(
                    f"• {s.get('source', 'Unknown')} (chunk {s.get('chunk_index', '?')})"
                    for s in sources[:3]
                )
                embed.add_field(name="Sources", value=source_text[:1024], inline=False)

            embed.set_footer(text=f"Confidence: {confidence:.0%}")

            await message.reply(embed=embed, mention_author=False)

        elif isinstance(result, dict) and "detail" in result:
            # Q&A failed -- might need issue creation
            await message.reply(
                f" I couldn't find a confirmed answer for that. "
                f"If this is a problem, use `{config.COMMAND_PREFIX}issue <description>` to report it.",
                mention_author=False,
            )
        else:
            await message.reply(" Sorry, I couldn't process that question right now.", mention_author=False)


async def handle_dm(message: discord.Message):
    """Handle a DM -- treat as a question or status check."""
    content = message.content.strip()

    if content.lower().startswith("status"):
        await handle_status_dm(message)
    else:
        # Treat as a question
        await handle_channel_message(message)


async def handle_status_dm(message: discord.Message):
    """Handle a status request via DM."""
    embed = discord.Embed(
        title="Team Status",
        description="I can help you check your team's status! Use the slash commands in the hackathon channel.",
        color=config.COLOR_INFO,
    )
    embed.add_field(
        name="Available Commands",
        value=(
            f"`{config.COMMAND_PREFIX}status` -- Your team's submission status\n"
            f"`{config.COMMAND_PREFIX}issue <desc>` -- Report an issue\n"
            f"`{config.COMMAND_PREFIX}help` -- All commands\n"
        ),
        inline=False,
    )
    await message.reply(embed=embed, mention_author=False)


# ─── Commands ─────────────────────────────────────────────


@bot.command(name="commands", help="Show all available commands")
async def commands_command(ctx: commands.Context):
    """Show help for all commands."""
    embed = discord.Embed(
        title=f"{config.BOT_NAME} Commands",
        description="Here's what I can do:",
        color=config.COLOR_INFO,
    )

    commands_list = [
        (f"`{config.COMMAND_PREFIX}commands`", "Show all commands"),
        (f"`{config.COMMAND_PREFIX}ask <question>`", "Ask a question about the hackathon rules"),
        (f"`{config.COMMAND_PREFIX}issue <description>`", "Report an issue or blocker"),
        (f"`{config.COMMAND_PREFIX}status`", "Check your team's submission status"),
        (f"`{config.COMMAND_PREFIX}escalations`", "View the escalation queue (organizer)"),
        (f"`{config.COMMAND_PREFIX}mentor <issue_id>`", "Request mentor allocation"),
    ]

    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)

    embed.set_footer(text="You can also just type a question in the hackathon channel!")
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="ask", help="Ask a question about hackathon rules")
async def ask_command(ctx: commands.Context, *, question: str):
    """Ask a question -- forwards to RAG pipeline."""
    async with ctx.typing():
        result = await api_request("POST", "/qa", json_data={"question": question})

        if isinstance(result, dict) and "answer" in result:
            answer = result["answer"]
            confidence = result.get("confidence", 0.0)
            sources = result.get("sources", [])

            embed = discord.Embed(
                title="Answer",
                description=answer[:2000],
                color=config.COLOR_SUCCESS if confidence > 0.5 else config.COLOR_WARNING,
            )

            if sources:
                source_text = "\n".join(
                    f"• {s.get('source', 'Unknown')}" for s in sources[:3]
                )
                embed.add_field(name="Sources", value=source_text[:1024], inline=False)

            embed.set_footer(text=f"Confidence: {confidence:.0%}")
            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply(
                " I couldn't find a confirmed answer. "
                f"Try rephrasing, or use `{config.COMMAND_PREFIX}issue` to report a problem.",
                mention_author=False,
            )


@bot.command(name="issue", help="Report an issue or blocker")
async def issue_command(ctx: commands.Context, *, description: str):
    """Create an issue -- forwards to POST /issues."""
    if len(description) < 10:
        await ctx.reply(" Issue description must be at least 10 characters.", mention_author=False)
        return

    async with ctx.typing():
        # Try to find the participant by Discord handle
        discord_handle = ctx.author.name

        # Search for participant
        participants = await api_request("GET", "/participants", params={"search": discord_handle})

        participant_id = None
        if isinstance(participants, list):
            for p in participants:
                if p.get("discord_handle") == discord_handle:
                    participant_id = p.get("id")
                    break

        if not participant_id:
            # Try matching by name
            if isinstance(participants, list):
                for p in participants:
                    if discord_handle.lower() in p.get("name", "").lower():
                        participant_id = p.get("id")
                        break

        if not participant_id:
            await ctx.reply(
                " I couldn't find your participant account. "
                "Make sure your Discord handle matches your registration.",
                mention_author=False,
            )
            return

        # Create the issue
        result = await api_request("POST", "/issues", json_data={
            "description": description,
            "category": "discord_report",
            "severity": 0.5,
            "is_blocking": False,
        })

        if isinstance(result, dict) and "id" in result:
            embed = discord.Embed(
                title="Issue Created",
                description=f"Your issue has been reported and will be reviewed.",
                color=config.COLOR_SUCCESS,
            )
            embed.add_field(name="Issue ID", value=str(result["id"])[:8], inline=True)
            embed.add_field(name="Status", value=result.get("status", "open"), inline=True)
            embed.add_field(name="Description", value=description[:500], inline=False)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            error_msg = result.get("detail", "Unknown error") if isinstance(result, dict) else str(result)
            await ctx.reply(f" Failed to create issue: {error_msg}", mention_author=False)


@bot.command(name="status", help="Check team submission status")
async def status_command(ctx: commands.Context):
    """Check the team's submission status."""
    async with ctx.typing():
        # Find participant by Discord handle
        discord_handle = ctx.author.name
        participants = await api_request("GET", "/participants", params={"search": discord_handle})

        team_id = None
        if isinstance(participants, list):
            for p in participants:
                if p.get("discord_handle") == discord_handle or discord_handle.lower() in p.get("name", "").lower():
                    team_id = p.get("team_id")
                    break

        if not team_id:
            await ctx.reply(" I couldn't find your team. Are you registered?", mention_author=False)
            return

        # Get team details
        team = await api_request("GET", f"/teams/{team_id}")

        if isinstance(team, dict) and "name" in team:
            embed = discord.Embed(
                title=f"Team: {team.get('name', 'Unknown')}",
                color=config.COLOR_INFO,
            )
            embed.add_field(
                name="Submission Status",
                value=team.get("submission_status", "unknown"),
                inline=True,
            )
            embed.add_field(
                name="Readiness",
                value=f"{team.get('readiness_pct', 0):.0f}%",
                inline=True,
            )

            # Try to get submission details
            sub = await api_request("GET", f"/submissions/mine")
            if isinstance(sub, dict) and "completeness_pct" in sub:
                embed.add_field(
                    name="Completeness",
                    value=f"{sub['completeness_pct']:.0f}%",
                    inline=True,
                )
                missing = []
                if not sub.get("repo_url"):
                    missing.append("repo_url")
                if not sub.get("demo_url"):
                    missing.append("demo_url")
                if not sub.get("description"):
                    missing.append("description")
                if not sub.get("readme_url"):
                    missing.append("readme_url")
                if missing:
                    embed.add_field(
                        name="Missing Fields",
                        value=", ".join(missing),
                        inline=False,
                    )

            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply(" Couldn't fetch team status.", mention_author=False)


@bot.command(name="escalations", help="View escalation queue (organizer only)")
async def escalations_command(ctx: commands.Context):
    """View the escalation queue."""
    async with ctx.typing():
        result = await api_request("GET", "/escalations")

        if isinstance(result, list):
            if not result:
                await ctx.reply(" No open escalations.", mention_author=False)
                return

            embed = discord.Embed(
                title="Escalation Queue",
                description=f"{len(result)} open escalation(s)",
                color=config.COLOR_WARNING,
            )

            for esc in result[:5]:
                issue = esc.get("issue", {})
                embed.add_field(
                    name=f"#{str(esc.get('id', ''))[:8]} (urgency: {esc.get('urgency_score', 0):.2f})",
                    value=(
                        f"**{issue.get('category', 'general')}**: "
                        f"{issue.get('description', 'No description')[:100]}"
                    ),
                    inline=False,
                )

            if len(result) > 5:
                embed.set_footer(text=f"...and {len(result) - 5} more")

            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply(" Couldn't fetch escalations.", mention_author=False)


@bot.command(name="mentor", help="Request mentor allocation for an issue")
async def mentor_command(ctx: commands.Context, issue_id: str):
    """Request a mentor for an issue."""
    async with ctx.typing():
        result = await api_request("POST", "/mentor-allocations", json_data={
            "issue_id": issue_id,
        })

        if isinstance(result, dict) and "id" in result:
            embed = discord.Embed(
                title="Mentor Requested",
                description=f"A mentor has been proposed for your issue.",
                color=config.COLOR_SUCCESS,
            )
            embed.add_field(name="Allocation ID", value=str(result["id"])[:8], inline=True)
            embed.add_field(name="Status", value=result.get("status", "proposed"), inline=True)
            if result.get("mentor"):
                embed.add_field(
                    name="Mentor",
                    value=result["mentor"].get("name", "Unknown"),
                    inline=True,
                )
            await ctx.reply(embed=embed, mention_author=False)
        else:
            error_msg = result.get("detail", "Unknown error") if isinstance(result, dict) else str(result)
            await ctx.reply(f" Failed to request mentor: {error_msg}", mention_author=False)


# ─── Notification Delivery Loop ───────────────────────────


@tasks.loop(seconds=30)
async def notification_loop():
    """Periodically fetch and deliver pending notifications via Discord DM."""
    try:
        # Fetch pending notifications from backend
        result = await api_request("GET", "/notifications/pending")

        if not isinstance(result, list):
            return

        for notif in result:
            recipient_id = notif.get("recipient_id")
            content = notif.get("content", "")
            notification_id = notif.get("id")

            if not recipient_id or not content:
                continue

            # Find the Discord user by participant ID
            participant = await api_request("GET", f"/participants/{recipient_id}")

            if not isinstance(participant, dict):
                continue

            discord_handle = participant.get("discord_handle")
            if not discord_handle:
                continue

            # Find Discord member
            guild = bot.get_guild(config.DISCORD_CHANNEL_ID)
            if not guild:
                # Try to find any guild the bot is in
                for g in bot.guilds:
                    guild = g
                    break

            if not guild:
                continue

            # Search for member by name/handle
            member = None
            for m in guild.members:
                if m.name == discord_handle or m.display_name == discord_handle:
                    member = m
                    break

            if not member:
                # Try partial match
                for m in guild.members:
                    if discord_handle.lower() in m.name.lower():
                        member = m
                        break

            if not member:
                logger.warning("Could not find Discord member for handle: %s", discord_handle)
                continue

            # Send DM
            try:
                embed = discord.Embed(
                    title="Notification from Pulse",
                    description=content[:2000],
                    color=config.COLOR_INFO,
                )
                embed.set_footer(text="Hackathon Concierge")

                await member.send(embed=embed)

                # Mark as delivered
                await api_request(
                    "PATCH",
                    f"/notifications/{notification_id}/read",
                )

                logger.info("Delivered notification %s to %s", notification_id, discord_handle)

            except discord.Forbidden:
                logger.warning("Cannot DM user %s (DMs disabled)", discord_handle)
            except Exception as e:
                logger.error("Failed to send DM to %s: %s", discord_handle, e)

    except Exception as e:
        logger.error("Notification loop error: %s", e)


@notification_loop.before_loop
async def before_notification_loop():
    """Wait for bot to be ready before starting notification loop."""
    await bot.wait_until_ready()


# ─── Entry Point ──────────────────────────────────────────


def run_bot():
    """Run the Discord bot."""
    if not config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set. Bot cannot start.")
        logger.info("Set DISCORD_TOKEN in your .env file to enable Discord integration.")
        return

    logger.info("Starting Pulse Discord Bot...")
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
