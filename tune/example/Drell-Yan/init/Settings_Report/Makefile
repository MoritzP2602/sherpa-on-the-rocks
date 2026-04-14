Settings_Report.html: Settings_Report.md
	pandoc -s -o Settings_Report.html -c Style.css Settings_Report.md

Settings_Report.org: Settings_Report.md
	pandoc -f markdown -t org -c Style.css -o Settings_Report.org Settings_Report.md

clean:
	rm -f Settings_Report.html

.PHONY: clean