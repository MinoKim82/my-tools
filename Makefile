.PHONY: help list link unlink link-skill unlink-skill test

BIN_DIR := $(HOME)/.local/bin
SKILL_DIR := $(HOME)/.gemini/config/skills

help:
	@echo "Available commands in my-tools:"
	@echo "  make list                       - List all registered tools in ./tools/"
	@echo "  make link tool=<name>           - Symlink CLI entry point to $(BIN_DIR)/<name>"
	@echo "  make unlink tool=<name>         - Remove CLI symlink from $(BIN_DIR)/<name>"
	@echo "  make link-skill tool=<name>     - Symlink tool skill to $(SKILL_DIR)/<name>"
	@echo "  make unlink-skill tool=<name>   - Remove tool skill symlink from $(SKILL_DIR)/<name>"
	@echo "  make test                       - Run test suites across tools (if available)"

list:
	@echo "=== Registered Tools in ./tools/ ==="
	@if [ -d "tools" ]; then \
		for dir in tools/*; do \
			if [ -d "$$dir" ]; then \
				tool_name=$$(basename "$$dir"); \
				readme="$$dir/README.md"; \
				desc="No README.md found"; \
				if [ -f "$$readme" ]; then \
					desc=$$(head -n 5 "$$readme" | grep -v '^#' | sed '/^[[:space:]]*$$/d' | head -n 1); \
				fi; \
				has_skill="[ ]"; \
				if [ -d "$$dir/skill" ] && [ -f "$$dir/skill/SKILL.md" ]; then \
					has_skill="[Skill: OK]"; \
				fi; \
				printf "  • %-20s %-12s : %s\n" "$$tool_name" "$$has_skill" "$$desc"; \
			fi; \
		done; \
	else \
		echo "No tools/ directory yet."; \
	fi

link:
	@if [ -z "$(tool)" ]; then \
		echo "Error: Please specify tool=<name>, e.g.: make link tool=my-script"; \
		exit 1; \
	fi
	@mkdir -p $(BIN_DIR)
	@tool_dir="tools/$(tool)"; \
	if [ ! -d "$$tool_dir" ]; then \
		echo "Error: Tool directory '$$tool_dir' not found."; \
		exit 1; \
	fi; \
	entry=""; \
	if [ -f "$$tool_dir/src/$(tool).sh" ]; then \
		entry="$$tool_dir/src/$(tool).sh"; \
	elif [ -f "$$tool_dir/src/main.py" ]; then \
		entry="$$tool_dir/src/main.py"; \
	elif [ -f "$$tool_dir/src/bin/$(tool)" ]; then \
		entry="$$tool_dir/src/bin/$(tool)"; \
	elif [ -f "$$tool_dir/src/index.js" ]; then \
		entry="$$tool_dir/src/index.js"; \
	elif [ -f "$$tool_dir/$(tool).sh" ]; then \
		entry="$$tool_dir/$(tool).sh"; \
	elif [ -f "$$tool_dir/main.py" ]; then \
		entry="$$tool_dir/main.py"; \
	elif [ -f "$$tool_dir/bin/$(tool)" ]; then \
		entry="$$tool_dir/bin/$(tool)"; \
	elif [ -f "$$tool_dir/index.js" ]; then \
		entry="$$tool_dir/index.js"; \
	else \
		echo "Error: Could not automatically detect entry point in $$tool_dir/src or $$tool_dir (expected $(tool).sh, main.py, or bin/$(tool))."; \
		exit 1; \
	fi; \
	chmod +x "$$entry"; \
	ln -sf "$$(pwd)/$$entry" "$(BIN_DIR)/$(tool)"; \
	echo "Successfully linked CLI: $$(pwd)/$$entry -> $(BIN_DIR)/$(tool)"

unlink:
	@if [ -z "$(tool)" ]; then \
		echo "Error: Please specify tool=<name>, e.g.: make unlink tool=my-script"; \
		exit 1; \
	fi
	@if [ -L "$(BIN_DIR)/$(tool)" ]; then \
		rm "$(BIN_DIR)/$(tool)"; \
		echo "Removed CLI symlink $(BIN_DIR)/$(tool)"; \
	else \
		echo "No CLI symlink found at $(BIN_DIR)/$(tool)"; \
	fi

link-skill:
	@if [ -z "$(tool)" ]; then \
		echo "Error: Please specify tool=<name>, e.g.: make link-skill tool=my-script"; \
		exit 1; \
	fi
	@skill_dir="tools/$(tool)/skill"; \
	if [ ! -d "$$skill_dir" ] || [ ! -f "$$skill_dir/SKILL.md" ]; then \
		echo "Error: Skill directory '$$skill_dir' or SKILL.md not found."; \
		exit 1; \
	fi; \
	mkdir -p $(SKILL_DIR); \
	ln -sfn "$$(pwd)/$$skill_dir" "$(SKILL_DIR)/$(tool)"; \
	echo "Successfully linked Agent Skill: $$(pwd)/$$skill_dir -> $(SKILL_DIR)/$(tool)"

unlink-skill:
	@if [ -z "$(tool)" ]; then \
		echo "Error: Please specify tool=<name>, e.g.: make unlink-skill tool=my-script"; \
		exit 1; \
	fi
	@if [ -L "$(SKILL_DIR)/$(tool)" ]; then \
		rm "$(SKILL_DIR)/$(tool)"; \
		echo "Removed Skill symlink $(SKILL_DIR)/$(tool)"; \
	else \
		echo "No Skill symlink found at $(SKILL_DIR)/$(tool)"; \
	fi
