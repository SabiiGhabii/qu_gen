PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS libraries(
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL,
	version TEXT,
	scanned_at TEXT DEFAULT (datetime('now')),
	hash TEXT
);

CREATE TABLE IF NOT EXISTS symbols(
	id INTEGER PRIMARY KEY,
	library_id INTEGER NOT NULL,
	qualname TEXT NOT NULL,
	objtype TEXT NOT NULL,
	module TEXT NOT NULL,
	owner TEXT,
	is_public INTEGER NOT NULL,
	doc_hash TEXT,
	sig_hash TEXT,
	FOREIGN KEY(library_id) REFERENCES libraries(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_symbols on symbols(library_id, qualname);

CREATE TABLE IF NOT EXISTS signatures(
	id INTEGER PRIMARY KEY,
	symbol_id INTEGER NOT NULL,
	signature TEXT,
	params_json TEXT,
	returns_text TEXT,
	FOREIGN KEY(symbol_id) REFERENCES symbols(id)
);

CREATE TABLE IF NOT EXISTS docstrings(
	id INTEGER PRIMARY KEY,
	symbol_id INTEGER NOT NULL,
	summary TEXT,
	params_json TEXT,
	returns_json TEXT,
	raw TEXT,
	FOREIGN KEY(symbol_id) REFERENCES symbols(id)
);

CREATE TABLE IF NOT EXISTS examples(
	id INTEGER PRIMARY KEY,
	symbol_id INTEGER,
	code TEXT NOT NULL,
	source TEXT,
	path TEXT,
	line_start INTEGER,
	hash TEXT,
	FOREIGN KEY(symbol_id) REFERENCES symbols(id)
);

CREATE TABLE IF NOT EXISTS ontology_versions(
	id INTEGER PRIMARY KEY,
	version TEXT NOT NULL,
	created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS traits(
	id INTEGER PRIMARY KEY,
	name TEXT UNIQUE NOT NULL,
	king TEXT NOT NULL,
	category TEXT,
	description TEXT
);

CREATE TABLE IF NOT EXISTS trait_enums(
	id INTEGER PRIMARY KEY,
	trait_id INTEGER NOT NULL,
	code INTEGER NOT NULL,
	label TEXT NOT NULL,
	UNIQUE(trait_id, code),
	FOREIGN KEY(trait_id) REFERENCES traits(id)
);

CREATE TABLE IF NOT EXISTS profiles(
	id INTEGER PRIMARY KEY,
	name TEXT UNIQUE NOT NULL,
	description TEXT
);

CREATE TABLE IF NOT EXISTS profile_facts(
	profile_id INTEGER NOT NULL,
	is_pre INTEGER NOT NULL,
	trait_id INTEGER NOT NULL,
	val_enum_code INTEGER,
	val_i INTEGER,
	min_i INTEGER, max_i INTEGER,
	min_f REAL, max_f REAL,
	PRIMARY KEY(profile_id, is_pre, trait_id),
	FOREIGN KEY(profile_id) REFERENCES profiles(id),
	FOREIGN KEY(trait_id) REFERENCES traits(id)
);

CREATE TABLE IF NOT EXISTS cards(
	id INTEGER PRIMARY KEY,
	symbol_id INTEGER NOT NULL,
	ontology_version_id INTEGER NOT NULL,
	cost INTEGER,
	flags_blob BLOB,
	ir_blob BLOB NOT NULL,
	hash TEXT NOT NULL,
	profiles_json TEXT,
	created_at TEXT DEFAULT (datetime('now')),
	FOREIGN KEY(symbol_id) REFERENCES symbols(id),
	FOREIGN KEY(ontology_version_id) REFERENCES ontology_versions(id)
);

CREATE TABLE IF NOT EXISTS card_facts(
	card_id INTEGER NOT NULL,
	is_pre INTEGER NOT NULL,
	trait_id INTEGER NOT NULL,
	val_enum_code INTEGER,
	val_i INTEGER,
	min_i INTEGER, max_i INTEGER,
	min_f REAL, max_f REAL,
	PRIMARY KEY(card_id, is_pre, trait_id),
	FOREIGN KEY(card_id) REFERENCES cards(id),
	FOREIGN KEY(trait_id) REFERENCES traits(id)
);

CREATE INDEX IF NOT EXISTS ix_card_facts_trait ON card_facts(trait_id, is_pre, val_enum_code, val_i);
CREATE INDEX IF NOT EXISTS ix_cards_symbol ON cards(symbol_id);