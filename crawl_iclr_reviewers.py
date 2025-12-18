"""
Crawl all reviewer information for ICLR submissions from OpenReview API.

Usage:
    python crawl_iclr_reviewers.py --year 2026 --output reviewers.json
"""

import requests
import json
import time
import argparse
from typing import Dict, List, Optional
from collections import defaultdict
from tqdm import tqdm


class OpenReviewCrawler:
    BASE_URL = "https://api2.openreview.net"
    
    def __init__(self, year: int = 2026):
        self.year = year
        self.venue = f"ICLR.cc/{year}/Conference"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
    
    def get_all_submissions(self, limit: int = 1000) -> List[Dict]:
        """Get all submissions for the conference."""
        submissions = []
        offset = 0
        
        print(f"Fetching submissions for {self.venue}...")
        
        while True:
            url = f"{self.BASE_URL}/notes"
            params = {
                "content.venue": self.venue,
                "limit": limit,
                "offset": offset
            }
            
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                notes = data.get("notes", [])
                if not notes:
                    break
                    
                submissions.extend(notes)
                print(f"  Fetched {len(submissions)} submissions so far...")
                
                if len(notes) < limit:
                    break
                    
                offset += limit
                time.sleep(0.5)  # Rate limiting
                
            except requests.RequestException as e:
                print(f"Error fetching submissions: {e}")
                break
        
        print(f"Total submissions found: {len(submissions)}")
        return submissions
    
    def get_submission_numbers(self) -> List[int]:
        """Get all submission numbers by querying the groups API."""
        submission_numbers = []
        
        # Try to get submission groups
        url = f"{self.BASE_URL}/groups"
        params = {
            "prefix": f"{self.venue}/Submission",
            "limit": 10000
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            groups = data.get("groups", [])
            for group in groups:
                group_id = group.get("id", "")
                # Extract submission number from group ID like "ICLR.cc/2026/Conference/Submission123"
                if "/Submission" in group_id and "/Reviewer" not in group_id:
                    parts = group_id.split("/Submission")
                    if len(parts) > 1:
                        num_part = parts[1].split("/")[0]
                        if num_part.isdigit():
                            submission_numbers.append(int(num_part))
            
            submission_numbers = sorted(set(submission_numbers))
            
        except requests.RequestException as e:
            print(f"Error fetching submission groups: {e}")
        
        return submission_numbers
    
    def get_reviewer_groups_for_submission(self, submission_number: int) -> List[str]:
        """Get all reviewer group IDs for a specific submission."""
        reviewer_ids = []
        
        url = f"{self.BASE_URL}/groups"
        params = {
            "prefix": f"{self.venue}/Submission{submission_number}/Reviewer_",
            "limit": 100
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            groups = data.get("groups", [])
            for group in groups:
                group_id = group.get("id", "")
                # Extract reviewer ID like "HydY" from "ICLR.cc/2026/Conference/Submission21870/Reviewer_HydY"
                if "/Reviewer_" in group_id:
                    reviewer_id = group_id.split("/Reviewer_")[-1]
                    if reviewer_id:
                        reviewer_ids.append(reviewer_id)
                        
        except requests.RequestException as e:
            print(f"Error fetching reviewers for submission {submission_number}: {e}")
        
        return reviewer_ids
    
    def get_reviewer_profile(self, submission_number: int, reviewer_id: str) -> Optional[Dict]:
        """Get reviewer profile information."""
        group = f"{self.venue}/Submission{submission_number}/Reviewer_{reviewer_id}"
        url = f"{self.BASE_URL}/profiles/search"
        params = {"group": group}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            profiles = data.get("profiles", [])
            if profiles:
                return profiles[0]
                
        except requests.RequestException as e:
            print(f"Error fetching profile for {group}: {e}")
        
        return None
    
    def extract_profile_info(self, profile: Dict) -> Dict:
        """Extract relevant information from a profile."""
        content = profile.get("content", {})
        
        # Get name
        names = content.get("names", [])
        name = names[0].get("fullname", "Unknown") if names else "Unknown"
        
        # Get current position and institution
        history = content.get("history", [])
        current_position = None
        current_institution = None
        if history:
            # Sort by start date descending to get most recent
            sorted_history = sorted(history, key=lambda x: x.get("start", 0), reverse=True)
            if sorted_history:
                current = sorted_history[0]
                current_position = current.get("position")
                inst = current.get("institution", {})
                current_institution = inst.get("name")
        
        # Get Google Scholar
        gscholar = content.get("gscholar", "")
        
        # Get emails (masked in API response)
        emails = content.get("emails", [])
        
        return {
            "id": profile.get("id"),
            "name": name,
            "position": current_position,
            "institution": current_institution,
            "gscholar": gscholar,
            "emails": emails,
            "full_profile": profile
        }
    
    def crawl_all_reviewers(self, max_submissions: Optional[int] = None) -> Dict:
        """Crawl all reviewer information for all submissions."""
        results = {
            "venue": self.venue,
            "submissions": {},
            "unique_reviewers": {},
            "stats": {
                "total_submissions": 0,
                "total_reviewer_assignments": 0,
                "unique_reviewers": 0
            }
        }
        
        # Get all submission numbers
        print("Step 1: Getting all submission numbers...")
        submission_numbers = self.get_submission_numbers()
        
        if not submission_numbers:
            print("No submissions found via groups API. Trying alternative method...")
            # Try a range-based approach as fallback
            submission_numbers = list(range(1, 30000))  # Adjust range as needed
        
        if max_submissions:
            submission_numbers = submission_numbers[:max_submissions]
        
        print(f"Will check {len(submission_numbers)} submissions...")
        
        # For each submission, get reviewers
        print("\nStep 2: Fetching reviewers for each submission...")
        all_reviewers = defaultdict(list)
        
        for sub_num in tqdm(submission_numbers, desc="Processing submissions"):
            reviewer_ids = self.get_reviewer_groups_for_submission(sub_num)
            
            if reviewer_ids:
                results["submissions"][sub_num] = {
                    "reviewer_ids": reviewer_ids,
                    "reviewers": []
                }
                
                for rev_id in reviewer_ids:
                    all_reviewers[(sub_num, rev_id)] = None
            
            time.sleep(0.1)  # Rate limiting
        
        print(f"\nFound {len(results['submissions'])} submissions with reviewers")
        print(f"Total reviewer assignments: {len(all_reviewers)}")
        
        # Fetch reviewer profiles
        print("\nStep 3: Fetching reviewer profiles...")
        unique_profiles = {}
        
        for (sub_num, rev_id) in tqdm(all_reviewers.keys(), desc="Fetching profiles"):
            profile = self.get_reviewer_profile(sub_num, rev_id)
            
            if profile:
                profile_info = self.extract_profile_info(profile)
                profile_id = profile_info["id"]
                
                # Add to submission's reviewer list
                results["submissions"][sub_num]["reviewers"].append({
                    "reviewer_id": rev_id,
                    "profile_id": profile_id,
                    "name": profile_info["name"],
                    "institution": profile_info["institution"]
                })
                
                # Add to unique reviewers
                if profile_id not in unique_profiles:
                    unique_profiles[profile_id] = profile_info
            
            time.sleep(0.2)  # Rate limiting
        
        results["unique_reviewers"] = unique_profiles
        results["stats"]["total_submissions"] = len(results["submissions"])
        results["stats"]["total_reviewer_assignments"] = len(all_reviewers)
        results["stats"]["unique_reviewers"] = len(unique_profiles)
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Crawl ICLR reviewer information from OpenReview")
    parser.add_argument("--year", type=int, default=2026, help="ICLR year (default: 2026)")
    parser.add_argument("--output", type=str, default="iclr_reviewers.json", help="Output JSON file")
    parser.add_argument("--max-submissions", type=int, default=None, 
                        help="Maximum number of submissions to process (for testing)")
    
    args = parser.parse_args()
    
    print(f"=" * 60)
    print(f"ICLR {args.year} Reviewer Crawler")
    print(f"=" * 60)
    
    crawler = OpenReviewCrawler(year=args.year)
    results = crawler.crawl_all_reviewers(max_submissions=args.max_submissions)
    
    # Save results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print("Crawling complete!")
    print(f"{'=' * 60}")
    print(f"Results saved to: {args.output}")
    print(f"\nStatistics:")
    print(f"  - Submissions with reviewers: {results['stats']['total_submissions']}")
    print(f"  - Total reviewer assignments: {results['stats']['total_reviewer_assignments']}")
    print(f"  - Unique reviewers: {results['stats']['unique_reviewers']}")


if __name__ == "__main__":
    main()






