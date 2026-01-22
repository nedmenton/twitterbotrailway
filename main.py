# SORSA CRYPTO INTELLIGENCE - RAILWAY DEPLOYMENT
# Automated weekly discovery of early-stage crypto projects

import requests
import pandas as pd
import time
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
import sqlite3
import os
from dataclasses import dataclass
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ScoringCriteria:
    """Data class to hold all scoring criteria"""
    follower_thresholds = [
        (0, 200), (200, 150), (400, 100), (600, 60), (800, 55),
        (1000, 50), (1200, 45), (1600, 40), (2000, 35), (2600, 30),
        (3200, 25), (4000, 20), (5000, 15), (6000, 10), (7000, 5),
        (8000, 2), (10000, 1)
    ]
    creation_date_thresholds = [
        (2, 200), (4, 150), (6, 100), (8, 60), (10, 55),
        (12, 50), (14, 45), (16, 40), (18, 35), (20, 30),
        (24, 25), (28, 20), (32, 15), (36, 10), (40, 5), (52, 2)
    ]
    link_scores = {'discord': 80, 'telegram': 10, 'website': 40}
    keyword_score = 50


class DatabaseManager:
    """Handles all database operations using SQLite"""

    def __init__(self, db_path: str = "crypto_intelligence.db"):
        self.db_path = os.path.abspath(db_path)
        print(f"📁 Database path: {self.db_path}")
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                handle TEXT UNIQUE NOT NULL,
                bio TEXT,
                followers_count INTEGER,
                creation_date TEXT,
                creation_weeks_old INTEGER,
                follower_score INTEGER,
                creation_score INTEGER,
                keyword_score INTEGER,
                link_score INTEGER,
                power_user_score INTEGER,
                total_score INTEGER,
                discovered_date TEXT,
                power_users_following TEXT,
                keywords_found TEXT,
                links_found TEXT,
                verified BOOLEAN,
                is_protected BOOLEAN,
                last_updated TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT,
                companies_discovered INTEGER,
                total_api_calls INTEGER,
                power_users_processed INTEGER,
                runtime_minutes REAL,
                batch_number INTEGER,
                filtered_followers INTEGER,
                filtered_age INTEGER
            )
        ''')
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM companies")
        company_count = cursor.fetchone()[0]
        conn.close()
        print(f"✅ Database initialized with {company_count} existing companies")

    def company_exists(self, handle: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM companies WHERE LOWER(handle) = LOWER(?)", (handle,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def get_all_handles(self) -> set:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT handle FROM companies")
            handles = {row[0].lower() for row in cursor.fetchall()}
            conn.close()
            return handles
        except Exception as e:
            print(f"Warning: Could not get existing handles: {e}")
            return set()

    def save_company(self, company_data: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO companies (
                name, handle, bio, followers_count, creation_date, creation_weeks_old,
                follower_score, creation_score, keyword_score, link_score, power_user_score,
                total_score, discovered_date, power_users_following, keywords_found,
                links_found, verified, is_protected, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            company_data['name'], company_data['handle'], company_data['bio'],
            company_data['followers_count'], company_data['creation_date'],
            company_data['creation_weeks_old'], company_data['follower_score'],
            company_data['creation_score'], company_data['keyword_score'],
            company_data['link_score'], company_data['power_user_score'],
            company_data['total_score'], company_data['discovered_date'],
            ','.join(company_data['power_users_following']),
            ','.join(company_data['keywords_found']),
            ','.join(company_data['links_found']),
            company_data['verified'], company_data['is_protected'],
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    def get_companies(self, min_score: int = 200) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            "SELECT * FROM companies WHERE total_score >= ? ORDER BY total_score DESC",
            conn, params=(min_score,)
        )
        conn.close()
        return df

    def save_api_run(self, run_data: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO api_runs (run_date, companies_discovered, total_api_calls, 
                                power_users_processed, runtime_minutes, batch_number,
                                filtered_followers, filtered_age)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_data['run_date'], run_data['companies_discovered'],
            run_data['total_api_calls'], run_data['power_users_processed'],
            run_data['runtime_minutes'], run_data.get('batch_number', 0),
            run_data.get('filtered_followers', 0), run_data.get('filtered_age', 0)
        ))
        conn.commit()
        conn.close()


class CryptoIntelligencePlatform:
    """Main platform class for crypto intelligence gathering"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sorsa.io/v2"  # SORSA API
        self.headers = {"ApiKey": api_key, "Accept": "application/json"}
        self.db = DatabaseManager()
        self.scoring = ScoringCriteria()

        # Power users with their signal scores
        self.power_users_scores = {
            "NTmoney": 100, "zhusu": 100, "AriannaSimpson": 100, "santiagoroel": 100, 
            "StaniKulechov": 100, "eddylazzarin": 100, "adampatel23": 100, "jbrukh": 100, 
            "spencernoon": 100, "MonetSupply": 90, "arjunblj": 100, "janehk": 100, 
            "Derekmw23": 100, "0xminion": 100, "MerschMax_": 100, "bneiluj": 100,
            "Iiterature": 100, "panekkkk": 100, "zoink": 100, "gpl_94": 90, 
            "WuCarra": 80, "bitcoinPalmer": 70, "Darrenlautf": 80, "john_c_palmer": 70, 
            "lmrankhan": 70, "WPeaster": 80, "bottomd0g": 70, "dApp_boi": 70, 
            "sethginns": 70, "RyanWatkins": 100, "CryptoMaestro": 80, "gabrieltanhl": 80,
            "fomosaurus": 70, "mayazi": 70, "litocoen": 70, "mrjasonchoi": 100, 
            "redphonecrypto": 80, "lalleclausen": 70, "QwQiao": 80, "Arthur_0x": 80, 
            "riabhutoria": 70, "pythianism": 70, "0xMaki": 100, "AustinBarack": 80, 
            "guywuolletjr": 70, "0x_Osprey": 80, "dberenzon": 100, "_kinjalbshah": 100, 
            "yanr0ux": 70, "Shaughnessy119": 80, "cuysheffield": 100, "RoyLearner": 70,
            "KyleSamani": 100, "nanexcool": 100, "austingriffith": 100, "0xmubaris": 70, 
            "richardchen39": 70, "pet3rpan_": 80, "Casey": 70, "Mable_Jiang": 100, 
            "tklocanas": 70, "AndrewSteinwold": 80, "joonian": 70, "ConvexMonster": 80, 
            "gmoneyNFT": 100, "carlosecgomes": 70, "thattallguy": 70, "trent_vanepps": 80,
            "Flynnjamm": 70, "pranksy": 100, "Jihoz_Axie": 100, "js_horne": 70, 
            "gabagooldoteth": 70, "GarrettCAllen": 80, "ASvanevik": 80, "polats": 70, 
            "0xstephb": 80, "heyellieday": 70, "__mikareyes": 70, "Rebecca_Mqamelo": 70,
            "vsinghdothings": 70, "mikedemarais": 70, "beaniemaxi": 80, "rleshner": 100, 
            "stablekwon": 100, "_trente_": 70, "0xmons": 70, "JosephTodaro_": 80, 
            "tonysheng": 100, "ai": 100, "mattysino": 70, "calchulus": 70, "MarkBeylin": 80, 
            "mg": 70, "masonnystrom": 70, "fvckrender": 60, "mhonkasalo": 70,
            "KeyboardMonkey3": 60, "scott_lew_is": 70, "loomdart": 60, "Paul_Burlage": 70,
            "camron_miraftab": 70, "DeezeFi": 70, "AlexMasmej": 90, "johnx25bd": 70, 
            "NazzMass": 70, "notscottmoore": 80, "garythung": 70, "thatguybg": 60, 
            "finn_meeks": 60, "cicici__ci": 60, "muhnkee": 60, "Block49Capital": 80,
            "0xedenau": 70, "jonwu_": 80, "simondlr": 90, "algofamily": 70, 
            "SOLBigBrain": 70, "AustinGreen": 70, "Zeneca_33": 100, "jkuanderulo": 70,
            "ViktorBunin": 90, "benjaminsimon97": 70, "JaschaSamadi": 70,
            "aeyakovenko": 80, "sandeepnailwal": 80, "dcfgod": 80, "balajis": 80,
            "rajgokal": 80, "0xMert_": 80, "samkazemian": 80, "PaulTaylorVC": 80,
            "TheOnlyNom": 80, "gdog97_": 80, "michaelh_0g": 80, "will__price": 80,
            "zmanian": 80, "sreeramkannan": 80, "gametheorizing": 80, "Melt_Dem": 80,
            "SimkinStepan": 80, "rushimanche": 80, "ekrahm": 80, "PrimordialAA": 80,
            "baalazamon": 80, "kashdhandam": 80, "mrblockw": 80, "chainyoda": 80,
            "comfycapital_": 80, "keoneHD": 80,
            "0xave": 80, "TusharJain_": 80, "tomhschmidt": 80, "nic__carter": 80,
            "mdudas": 80, "JReedRosenthal": 80, "jessewldn": 80, "Hootie_R": 80,
            "FranklinBi": 80, "evanbfish": 80, "brezshares": 80, "tolycrypto": 80,
            "alpackaP": 80, "simonkim_nft": 80, "ZeMariaMacedo": 80, "brevsin": 80,
            "CryptoHayes": 80, "avichal": 80, "MapleLeafCap": 80, "tekinsalimi": 80,
            "kaiynnе": 80, "yidagao": 80, "meigga": 80, "emmacui": 80, "DAnconia_Crypto": 80,
            "zacxbt": 80, "Defi0xJeff": 80,
            "_dshap": 80, "JasonYanowitz": 80, "MichaelIppo": 80, "SteimetzKinji": 80,
            "AvgJoesCrypto": 80, "defi_monk": 80, "0xCryptoSam": 80, "Solofunk_": 80,
            "dylangbane": 80, "0xMether": 80, "salveboccaccio": 80, "EffortCapital": 80,
            "Kunallegendd": 80, "jon_charb": 80, "shaundadevens": 80, "0xcarlosg": 80,
            "defi_kay_": 80, "marcarjoon": 80, "_ryanrconnor": 80, "smyyguy": 80,
            "WestieCapital": 80, "ItsFloe": 80, "PlagueObserver": 80, "luisri_": 80,
            "0xWeiler": 80,
        }
        self.power_users = list(self.power_users_scores.keys())

        self.crypto_keywords = [
            "nft", "cross-chain", "multi-chain", "data", "analytics", "aggregator", 
            "trading", "protocol", "tokenized", "amm", "dex", "optimisation", 
            "solution", "liquidity", "terra", "solana", "ethereum", "celo", 
            "dao", "perpetuals", "decentralized", "exchange", "derivatives", 
            "capital-efficient", "metaverse", "game", "gaming", "gamified", 
            "community", "art", "index", "insurance", "platform", 
            "layer 2", "web 3", "web3", "borrowing", "lending", "loans", 
            "staking", "collectibles", "marketplace", "risk", "api", 
            "virtual", "wallet", "payments", "prediction", "options", "privacy", 
            "smart contract", "infrastructure", "stablecoin", 
            "algorithmic", "farming", "synthetic", "yield", "arweave", "cosmos", 
            "defi", "credential", "souldbound", "layer", "collateralized", 
            "application", "dapp", "building", "composable", "modular", 
            "as-a-service", "monetization", "digital", "identity", "ownership", 
            "blockchain", "onchain", "on-chain", "no-code", "graph", "zkp", 
            "tools", "tooling", "service", "rwa", "real-world-assets"
        ]

    def extract_handle(self, account_data: Dict) -> str:
        screenName = account_data.get('screenName', '').strip()
        if screenName:
            return screenName
        screeName = account_data.get('screeName', '').strip()
        if screeName:
            return screeName
        name = account_data.get('name', '').strip()
        if name:
            handle = re.sub(r'[^\w\.]', '', name)
            if handle and len(handle) > 2:
                return handle
        user_id = account_data.get('id', '')
        if user_id:
            return f"user_{user_id}"
        return ''

    def get_new_following_7d(self, user_handle: str) -> Optional[List[Dict]]:
        url = f"{self.base_url}/new-following-7d"
        params = {"user_handle": user_handle}
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ {user_handle}: {len(data)} new follows")
                return data
            elif response.status_code == 404:
                logger.warning(f"⚠ {user_handle}: Not found in database")
                return []
            else:
                logger.error(f"✗ {user_handle}: Error {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ {user_handle}: Request error - {e}")
            return None

    def get_top_followers(self, user_handle: str) -> Optional[List[Dict]]:
        url = f"{self.base_url}/top-following/{user_handle}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"⚠ Could not get top followers for {user_handle}: {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Top followers error for {user_handle}: {e}")
            return []

    def calculate_account_age_weeks(self, created_at: str) -> int:
        try:
            if created_at:
                if created_at.endswith('Z'):
                    creation_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    creation_date = datetime.fromisoformat(created_at)
                creation_date = creation_date.replace(tzinfo=None)
                age_weeks = (datetime.now() - creation_date).days // 7
                return max(0, age_weeks)
        except Exception as e:
            logger.warning(f"Could not parse date {created_at}: {e}")
        return 999

    def score_follower_count(self, count: int) -> int:
        for threshold, score in self.scoring.follower_thresholds:
            if count <= threshold:
                return score
        return 0

    def score_creation_date(self, weeks_old: int) -> int:
        for threshold, score in self.scoring.creation_date_thresholds:
            if weeks_old <= threshold:
                return score
        return 0

    def find_keywords_in_bio(self, bio: str) -> Tuple[List[str], int]:
        if not bio:
            return [], 0
        bio_lower = bio.lower()
        found_keywords = []
        for keyword in self.crypto_keywords:
            if keyword.lower() in bio_lower:
                found_keywords.append(keyword)
        found_keywords = list(dict.fromkeys(found_keywords))
        return found_keywords, len(found_keywords) * self.scoring.keyword_score

    def find_links_in_bio(self, bio: str) -> Tuple[List[str], int]:
        if not bio:
            return [], 0
        found_links = []
        total_score = 0
        bio_lower = bio.lower()
        if any(word in bio_lower for word in ['discord', 'discord.gg', 'discord.com']):
            found_links.append('Discord Channel')
            total_score += self.scoring.link_scores['discord']
        if any(word in bio_lower for word in ['telegram', 't.me', 'tg://']):
            found_links.append('Telegram Channel')
            total_score += self.scoring.link_scores['telegram']
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, bio)
        if urls and not found_links:
            found_links.append('Website URL')
            total_score += self.scoring.link_scores['website']
        return found_links, total_score

    def check_power_user_followers(self, account_handle: str) -> Tuple[List[str], int]:
        top_followers = self.get_top_followers(account_handle)
        if not top_followers:
            return [], 0
        top_follower_handles = set()
        for follower in top_followers:
            handle = self.extract_handle(follower).lower()
            if handle:
                top_follower_handles.add(handle)
        power_user_matches = []
        total_score = 0
        for power_user in self.power_users:
            if power_user.lower() in top_follower_handles:
                power_user_matches.append(power_user)
                user_score = self.power_users_scores.get(power_user, 70)
                total_score += user_score
        return power_user_matches, total_score

    def score_account(self, account_data: Dict, discovered_by: str) -> Dict:
        handle = self.extract_handle(account_data)
        name = account_data.get('name', '')
        bio = account_data.get('description', '')
        followers_count = account_data.get('followersCount', 0)
        created_at = account_data.get('registerDate', '')
        verified = account_data.get('verified', False)
        is_protected = account_data.get('protected', False)

        weeks_old = self.calculate_account_age_weeks(created_at)
        follower_score = self.score_follower_count(followers_count)
        creation_score = self.score_creation_date(weeks_old)
        keywords_found, keyword_score = self.find_keywords_in_bio(bio)
        links_found, link_score = self.find_links_in_bio(bio)
        
        # FIXED: Skip the failing top-followers API call, just use discoverer
        power_users_following = [discovered_by]
        discoverer_score = self.power_users_scores.get(discovered_by, 70)
        power_user_score = discoverer_score

        total_score = follower_score + creation_score + keyword_score + link_score + power_user_score
        logger.info(f"  Scoring {handle}: F:{follower_score} + C:{creation_score} + K:{keyword_score} + L:{link_score} + P:{power_user_score} = {total_score}")

        return {
            'name': name, 'handle': handle, 'bio': bio,
            'followers_count': followers_count, 'creation_date': created_at,
            'creation_weeks_old': weeks_old, 'follower_score': follower_score,
            'creation_score': creation_score, 'keyword_score': keyword_score,
            'link_score': link_score, 'power_user_score': power_user_score,
            'total_score': total_score, 'discovered_date': datetime.now().isoformat(),
            'power_users_following': power_users_following,
            'keywords_found': keywords_found, 'links_found': links_found,
            'verified': verified, 'is_protected': is_protected
        }


def upload_to_google_sheet(df, sheet_id, sheet_name=None):
    """Upload results to Google Sheets"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_json = json.loads(os.environ['GOOGLE_SHEETS_CREDS'])
        creds = Credentials.from_service_account_info(creds_json, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        client = gspread.authorize(creds)

        sheet = client.open_by_key(sheet_id)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        if sheet_name is None:
            sheet_name = f"Results {timestamp}"

        try:
            worksheet = sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
        except Exception:
            worksheet = sheet.worksheet(sheet_name)
            worksheet.clear()

        # Prepare data
        sheets_df = df.copy()
        sheets_df['twitter_link'] = 'https://twitter.com/' + sheets_df['handle'].astype(str)
        sheets_df['handle'] = sheets_df['handle'].astype(str).apply(
            lambda x: x if str(x).startswith('@') else '@' + str(x)
        )
        
        columns = ['name', 'handle', 'twitter_link', 'total_score', 'followers_count', 'bio', 
                   'power_users_following', 'keywords_found', 'creation_date']
        available_columns = [col for col in columns if col in sheets_df.columns]
        sheets_df = sheets_df[available_columns]
        
        if 'bio' in sheets_df.columns:
            sheets_df['bio'] = sheets_df['bio'].astype(str).str[:200]

        # Clean values
        def clean_value(value):
            if value is None:
                return ""
            elif isinstance(value, (list, tuple)):
                return ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                return str(value)
            elif isinstance(value, bool):
                return str(value)
            else:
                cleaned = str(value).replace('\n', ' ').replace('\r', ' ')
                return cleaned[:500]

        data_to_upload = [sheets_df.columns.values.tolist()]
        for _, row in sheets_df.iterrows():
            cleaned_row = [clean_value(val) for val in row.values]
            data_to_upload.append(cleaned_row)

        worksheet.update('A1', data_to_upload)
        print(f"✅ Uploaded {len(df)} companies to Google Sheets!")
        print(f"🔗 Sheet: {sheet.url}")
        return True

    except Exception as e:
        print(f"❌ Error uploading to Google Sheets: {e}")
        return False


def weekly_automation():
    """Main function for weekly automation"""
    print("🤖 Starting weekly crypto intelligence run...")
    print(f"📅 Run date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    API_KEY = os.environ.get('SORSA_API_KEY', "ebd63ef7-b0bb-4bde-92e3-5ae87692c781")
    platform = CryptoIntelligencePlatform(API_KEY)

    existing_handles = platform.db.get_all_handles()
    print(f"🔍 Existing companies for deduplication: {len(existing_handles)}")
    print(f"🚀 Processing {len(platform.power_users)} users in batches...")

    all_users = list(platform.power_users_scores.keys())
    batch_size = 20
    total_new_discoveries = []
    total_duplicates_skipped = 0

    for batch_num in range(0, len(all_users), batch_size):
        end_idx = min(batch_num + batch_size, len(all_users))
        batch_users = all_users[batch_num:end_idx]
        batch_number = (batch_num // batch_size) + 1

        print(f"\n🔥 BATCH {batch_number}/{(len(all_users) + batch_size - 1) // batch_size}")
        print(f"👥 Processing users {batch_num+1}-{end_idx}")

        batch_start_time = datetime.now()
        batch_new_discoveries = []
        batch_duplicates = 0

        for i, power_user in enumerate(batch_users, 1):
            print(f"  [{i}/{len(batch_users)}] Processing @{power_user}...")

            new_follows = platform.get_new_following_7d(power_user)
            if new_follows is None or not new_follows:
                continue

            for account in new_follows:
                handle = platform.extract_handle(account)
                if not handle:
                    continue

                if handle.lower() in existing_handles:
                    batch_duplicates += 1
                    continue

                followers_count = account.get('followersCount', 0)
                created_at = account.get('registerDate', '')

                if followers_count > 5000 or platform.calculate_account_age_weeks(created_at) > 104:
                    continue

                try:
                    scored_account = platform.score_account(account, power_user)
                    if scored_account['total_score'] >= 200:
                        platform.db.save_company(scored_account)
                        batch_new_discoveries.append(scored_account)
                        existing_handles.add(handle.lower())
                        print(f"    ✅ {handle}: {scored_account['total_score']} points")
                except Exception as e:
                    logger.error(f"Error scoring {handle}: {e}")
                    continue

            time.sleep(1.0)

        batch_runtime = (datetime.now() - batch_start_time).total_seconds() / 60
        total_new_discoveries.extend(batch_new_discoveries)
        total_duplicates_skipped += batch_duplicates
        print(f"  ✅ Batch {batch_number}: {len(batch_new_discoveries)} new, {batch_duplicates} duplicates, {batch_runtime:.1f}min")

    # Final summary
    print(f"\n🎉 WEEKLY RUN COMPLETE!")
    print(f"🆕 Total NEW discoveries: {len(total_new_discoveries)}")
    print(f"🔄 Total duplicates skipped: {total_duplicates_skipped}")

    if total_new_discoveries:
        new_discoveries_df = pd.DataFrame(total_new_discoveries)

        print(f"\n🏆 TOP NEW DISCOVERIES THIS WEEK:")
        print("-" * 70)
        for discovery in total_new_discoveries[:10]:
            print(f"@{discovery['handle']} | Score: {discovery['total_score']} | "
                  f"Followers: {discovery['followers_count']:,}")

        # Save CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"NEW_WEEKLY_discoveries_{timestamp}.csv"
        new_discoveries_df.to_csv(new_filename, index=False)
        print(f"\n💾 NEW discoveries saved: {new_filename}")

        # Upload to Google Sheets
        if 'GOOGLE_SHEETS_ID' in os.environ and 'GOOGLE_SHEETS_CREDS' in os.environ:
            print("📊 Uploading to Google Sheets...")
            sheet_name = f"NEW Week {timestamp[:8]}"
            upload_to_google_sheet(new_discoveries_df, os.environ['GOOGLE_SHEETS_ID'], sheet_name)

        return new_discoveries_df
    else:
        print("🔍 No new high-scoring companies discovered this week")
        return pd.DataFrame()


if __name__ == "__main__":
    weekly_automation()
