# wombat_tags.py
# Handles management of 'tags' which are user defined groups of logs

import os
import json



class Tag:
  tag_dir = os.path.join(os.getenv('LOCALAPPDATA'),'WombatLogs','Tags')
  # Make sure the profile directory exists
  if not os.path.exists(tag_dir):
    os.makedirs(tag_dir)

  def __init__(self, name=None, notes=None, log_files=None, changes_made=False):
    self.log_files = log_files
    self.notes = notes
    self.name = name
    self.changes_made = changes_made

  # Locate and return all tags
  @classmethod
  def get_tags(self):
    tags = []
    with os.scandir(self.tag_dir) as entries:
      for ent in [e for e in entries if e.name.endswith('.wtg')]:
        ent_path = os.path.join(self.tag_dir, ent.name)
        with open(ent_path, 'r') as file:
          try:
            profile_data = json.load(file)
            this_profile = self(
              name=profile_data['name'],
              notes=profile_data['notes'],
              log_files=profile_data['log_files']
            )
            tags.append(this_profile)
          except Exception as e:
            print(f"[DEBUG] Error loading profile from file {ent.name}: {e}")

    return tags          


  def delete_tag(self):
    my_path = os.path.join(self.tag_dir, self.name + '.wtg')
    os.remove(my_path)

  def save(self):
    json_payload = {
      'name': self.name,
      'notes': self.notes,
      'log_files': self.log_files
    }
    my_path = os.path.join(self.tag_dir, self.name + '.wtg')
    with open(my_path, 'w') as outfile:
      json.dump(json_payload, outfile, indent=4)


  @classmethod
  def load(self, tag_name):
    my_path = os.path.join(self.tag_dir, tag_name + '.wtg')
    with open(my_path, 'r') as infile:
      file_data = json.load(infile)
    loaded_tag = self(name=tag_name, notes=file_data['notes'], log_files=file_data['log_files'])
    return loaded_tag








