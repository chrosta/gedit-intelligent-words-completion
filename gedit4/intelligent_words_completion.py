###
# Copyright (C) 2010, Jens Nyman (nymanjens.nj@gmail.com).
#--
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#--
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#--
# Words completion via [CTRL]+[SPACE] shortcut by Chrosta (rosta.zdenek@gmail.com).
###
import re, traceback, collections
from datetime import datetime as dt
from gi.repository import Gtk, Gio, Gedit, GObject, PeasGtk, Gdk

class IntelligentWordsCompletionPlugin(GObject.Object, Gedit.WindowActivatable, PeasGtk.Configurable):
    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self._index = 0
        self._words = []
        self._prefix = ""
        self._postfix = ""

    def do_create_configure_widget(self):
        return IntelligentTextCompletionOptions.get_instance().create_configure_dialog()

    def do_activate(self):
        """
        Activate plugin.
        """
        window = self.window
        callback = self._on_window_tab_added
        id_1 = window.connect("tab-added", callback)
        callback = self._on_window_tab_removed
        id_2 = window.connect("tab-removed", callback)
        window.intelligent_text_completion_id = (id_1, id_2)
        views = window.get_views()
        for view in views:
            self._connect_view(view, window)

    def do_deactivate(self):
        """
        Deactivate plugin.
        """
        window = self.window
        widgets = [window]
        widgets.extend(window.get_views())
        widgets.extend(window.get_documents())
        for widget in widgets:
            for handler_id in getattr(widget, 'intelligent_text_completion_id', []):
                widget.disconnect(handler_id)
            widget.intelligent_text_completion_id = None

    def _connect_view(self, view, window):
        """
        Connect to view's editing signals.
        """
        callback_p = self._on_view_key_press_event
        id_p = view.connect("key-press-event", callback_p, window)
        view.intelligent_text_completion_id = id_p
        #--
        callback_r = self._on_view_key_release_event
        id_r = view.connect("key-release-event", callback_r, window)
        view.intelligent_text_completion_id = id_r
        
    def _on_window_tab_added(self, window, tab):
        """
        Connect to signals of the document and view in tab.
        """
        view = tab.get_view()
        handler_id = getattr(view, 'intelligent_text_completion_id', None)
        if handler_id is None:
            self._connect_view(view, window)

    def _on_window_tab_removed(self, window, tab):
        pass

    def _check_prefix(self, prefix):
        flag = True
        if len(prefix) > 0:
            prefix = prefix.split("_") 
            for part in prefix:
                if len(part) > 0:
                    if flag:
                        flag = part.isalnum()
        return flag
        
    def _on_view_key_press_event(self, view, event, window):
        doc = window.get_active_document()
        #--
        # Starting word completion after CTRL+SPACE pressed!
        #--
        if (event.state == Gdk.ModifierType.CONTROL_MASK):
            if event.get_keycode().keycode == 65: # CTRL+SPACE
                if len(self._words) == 0:
                    self._index = 0
                    cursor = doc.get_iter_at_mark(doc.get_insert())
                    offset = cursor.get_line_offset()
                    copy = cursor.copy()
                    prefix = ""
                    index = 0
                    while self._check_prefix(prefix) and (offset - index) > 0:
                        index += 1
                        copy.set_line_offset(offset - index)
                        prefix = doc.get_text(copy, cursor, False)
                    if prefix[0:1].isalnum() or prefix[0:1] == "_": self._prefix = prefix
                    else: self._prefix = prefix[1:]
                    #--
                    # Reload text content from all buffers and parsing all words to unique list.
                    #--
                    all_words = []
                    docs = window.get_documents()
                    for d in docs:
                        start = d.get_start_iter()
                        end = d.get_end_iter()
                        text = d.get_text(start, end, False)
                        lines = text.split("\n")
                        for line in lines:
                            line = line.strip()
                            if line[:1] != '#':
                                line = re.sub('\s{2,}', " ", line)
                                for word in [[m.start(), m.end()] for m in re.finditer('\w*', line)]:
                                    word = line[word[0]:word[1]]
                                    word = word.strip()
                                    if len(word) > 1:
                                        all_words.append(word)
                    all_words.sort()
                    unique_words = []
                    for w in all_words:
                        if w not in unique_words:
                            unique_words.append(w)
                    #--
                    # Preparation of list suitable words.
                    #--
                    words_suggestions = {}
                    for w in unique_words:
                        if w[0:len(self._prefix)] == self._prefix:
                            try: x = words_suggestions[len(w)]
                            except KeyError: words_suggestions[len(w)] = []
                            words_suggestions[len(w)].append(w)
                    ordered_words_suggestions = collections.OrderedDict(sorted(words_suggestions.items()))
                    ordered_words_suggestions = [[k, v] for k, v in ordered_words_suggestions.items()]
                    prepared_words_suggestions = []
                    for k, v in ordered_words_suggestions:
                        for w in v:
                            prepared_words_suggestions.append(w)
                    #--
                    # Remove current complete word from suggestions.
                    #--
                    fixed_words_suggestions = []
                    for w in prepared_words_suggestions:
                        if w == self._prefix: continue
                        fixed_words_suggestions.append(w)
                    fixed_words_suggestions.append("")
                    self._words = fixed_words_suggestions
                    ### print("--[list]-->" + str(self._words))
                #--
                # So if words are available for completion...
                #--
                postfix = ""
                if len(self._words) > 0:
                    #--
                    # ...the indeterminate postfix is removed...
                    #--
                    cursor = doc.get_iter_at_mark(doc.get_insert())
                    while cursor.get_line_offset() != doc.get_end_iter().get_offset():
                        if (cursor.get_line_offset() + 1) < (cursor.get_chars_in_line() + 1):
                            copy = cursor.copy()
                            copy.set_line_offset(cursor.get_line_offset() + 1)
                            char = doc.get_text(cursor, copy, False)
                            if char.isalnum() or char == "_": doc.delete_interactive(cursor, copy, True)
                            else: break
                        else: break
                    #--
                    # ...and cycle through the appropriate words.
                    #--
                    try:
                        word = self._words[self._index]
                    except IndexError:
                        self._index = 0
                        word = self._words[self._index]
                    self._index += 1
                    #--
                    ### print("--[word]-->" + word)
                    postfix = word[len(self._prefix):]
                    self._postfix = postfix
                    #==
                    doc.insert(cursor, postfix, len(self._postfix))
                    cursor = doc.get_iter_at_mark(doc.get_insert())
                    cursor.set_line_offset((cursor.get_line_offset() - len(self._postfix)))
                    doc.place_cursor(cursor)
                    #==
        try:
            return self._handle_event(view, event, window)
        except:
            err = "Exception\n"
            err += traceback.format_exc()
            doc.set_text(err)
            
    def _on_view_key_release_event(self, view, event, window):
        doc = window.get_active_document()
        #--
        # Complete cycling between words after issuing CTRL.
        #-- 
        if event.get_keycode().keycode == 37:
            if len(self._postfix):
                cursor = doc.get_iter_at_mark(doc.get_insert())
                cursor.set_line_offset((cursor.get_line_offset() + len(self._postfix)))
                doc.place_cursor(cursor)
            #==
            self._postfix = ""
            self._words = []
            #==
    
    #--
    # Plugin core functions.
    #--
    def _handle_event(self, view, event, window):
        """
        Key press event.
        """
        #--
        # Get vars...
        #--
        # ...constants,
        ignore_whitespace = '\t '
        # ...get document,
        doc = window.get_active_document()
        # ...get cursor,
        cursor = doc.get_iter_at_mark(doc.get_insert())
        # ...get typed string,
        typed_string = event.string
        # ...get previous char,
        prev_char = None
        if not cursor.get_line_offset() == 0:
            prev_char_pos = cursor.copy()
            prev_char_pos.set_line_offset(cursor.get_line_offset() - 1)
            prev_char = doc.get_text(prev_char_pos, cursor, False)
        # ...get next char,
        next_char = None
        if not cursor.ends_line():
            next_char_pos = cursor.copy()
            next_char_pos.set_line_offset(cursor.get_line_offset() + 1)
            next_char = doc.get_text(cursor, next_char_pos, False)
        # ...get line before cursor,
        line_start = cursor.copy()
        line_start.set_line_offset(0)
        preceding_line = doc.get_text(line_start, cursor, False)
        # ...get line after cursor,
        line_end = cursor.copy()
        if not cursor.ends_line():
            line_end.forward_to_line_end()
        line_after = doc.get_text(cursor, line_end, False)
        # ...get whitespace in front of line,
        whitespace_pos = 0
        whitespace = ""
        while len(preceding_line) > whitespace_pos and preceding_line[whitespace_pos] in ignore_whitespace:
            whitespace += preceding_line[whitespace_pos]
            whitespace_pos += 1
        # ...get options.
        options = IntelligentTextCompletionOptions.get_instance()
        
        #--
        # Do not complete text after pasting text.
        #--
        if len(typed_string) > 1:
            return False
        typed_char = typed_string
        
        #--
        # Globals.
        #--
        open_close = {
            '"': '"',
            "'": "'",
            '(': ')',
            '{': '}',
            '[': ']',
        }
        
        #--
        # Selected text...
        #--
        bounds = doc.get_selection_bounds()
        if len(bounds) > 0:
            # ...auto-close brackets and quotes,
            if options.closeBracketsAndQuotes:
                for open, close in open_close.items():
                    if typed_char == open:
                        # ...get bounds data,
                        off1 = bounds[0].get_offset()
                        off2 = bounds[1].get_offset()
                        # ...add open char,
                        doc.place_cursor(bounds[0])
                        doc.insert_at_cursor(open)
                        # ...refresh cursor and move it,
                        cursor = doc.get_iter_at_mark(doc.get_insert())
                        cursor.set_offset(cursor.get_offset() + (off2 - off1))
                        doc.place_cursor(cursor)
                        # ...add close char.
                        doc.insert_at_cursor(close)
                        return True
            return False

        #--
        # Auto-close brackets and quotes.
        #--
        if options.closeBracketsAndQuotes and prev_char != '\\':
            """
            Detect python comments.
            """
            if typed_char == '"' and re.search('^[^"]*""$', preceding_line) and cursor.ends_line():
                return self._insert_at_cursor(typed_char + ' ', ' """')

            for check_char, add_char in open_close.items():
                #--
                # If character user is adding is the same as the one that
                # is auto-generated, remove the auto generated char...
                #--
                if typed_char == add_char:
                    if not cursor.ends_line():
                        if next_char == add_char:
                            if check_char != add_char:
                                # ...don't remove ) when it's probably not auto-generated.
                                preceding_check_chars = len(re.findall('\%s' % check_char, preceding_line))
                                preceding_add_chars = len(re.findall('\%s' % add_char, preceding_line))
                                following_check_chars = len(re.findall('\%s' % check_char, line_after))
                                following_add_chars = len(re.findall('\%s' % add_char, line_after))
                                if preceding_check_chars - preceding_add_chars > following_add_chars:
                                    continue
                                #--
                                # Don't remove ) when the line becomes complex.
                                #--
                                if following_check_chars > 0:
                                    continue
                            doc.delete(cursor, next_char_pos)
                            return False
                #--
                # Typed_char equals char we're looking for...
                #--
                if typed_char == check_char:
                    # ...check for unlogical adding,
                    if check_char == add_char:
                        # ...uneven number of check_char's in front,
                        if len(re.findall(check_char, preceding_line)) % 2 == 1:
                            continue
                        # ...uneven number of check_char's in back.
                        if len(re.findall(check_char, line_after)) % 2 == 1:
                            continue
                    # ...don't add add_char if it is used around text,
                    non_text_left =  ' \t\n\r,=+*:;.?!$&@%~<(){}[]-"\''
                    non_text_right = ' \t\n\r,=+*:;.?&@%~>)}]'
                    if not next_char and not check_char == "'":
                        #--
                        # If we're just typing with nothing on the right,
                        # adding is OK as long as it isn't a "'"...
                        #--
                        pass
                    elif (not prev_char or prev_char in non_text_left) and (not next_char or next_char in non_text_right):
                        # ...this char is surrounded by nothing or non-text, therefore, we can add autotext.
                        pass
                    elif check_char != add_char and (not next_char or next_char in non_text_right):
                        # ...this opening char has non-text on the right, therefore, we can add autotext.
                        pass
                    else:
                        continue
                    # ...insert add_char.
                    return self._insert_at_cursor(typed_char, add_char)
                #--
                # Check backspace...
                #--
                if event.keyval == 65288: # ...backspace.
                    if prev_char == check_char and next_char == add_char:
                        doc.delete(cursor, next_char_pos)

        #--
        # Auto-complete XML tags...
        #--
        if options.completeXML:
            if prev_char == "<" and typed_char == "/":
                start = doc.get_start_iter()
                preceding_document = doc.get_text(start, cursor, False)
                # ...analyse previous XML code,
                closing_tag = get_closing_xml_tag(preceding_document)
                if closing_tag:
                    # ...insert code,
                    return self._insert_at_cursor(typed_char + closing_tag + ">")
                else:
                    # ...do nothing.
                    return False

        #--
        # Detect lists...
        #--
        if options.detectLists:
            if event.keyval == 65293: # RETURN
                # ...constants,
                list_bullets = ['* ', '- ', '$ ', '> ', '+ ', '~ ']
                # ...cycle through all bullets,
                for bullet in list_bullets:
                    if len(preceding_line) >= whitespace_pos + len(bullet):
                        if preceding_line[whitespace_pos:whitespace_pos + len(bullet)] == bullet:
                            # ...endlist function by double enter.
                            if preceding_line == whitespace + bullet and bullet != '* ':
                                start = cursor.copy()
                                start.set_line_offset(len(whitespace))
                                doc.delete(start, cursor)
                                return True
                            return self._insert_at_cursor(typed_char + whitespace + bullet)

        #--
        # Detect java-like comment...
        #--
        if event.keyval == 65293: # RETURN
            # ...constants,
            comments = {
                '/**' : (' * ', ' */'),
                '/*'  : (' * ', ' */'),
            }
            # ...cycle through all types of comment.
            for comment_start, (comment_middle, comment_end) in comments.items():
                if preceding_line[whitespace_pos:] == comment_start:
                    add_middle = typed_char + whitespace + comment_middle
                    add_end = typed_char + whitespace + comment_end
                    return self._insert_at_cursor(add_middle, add_end)

        #--
        # Auto-indent after function/list...
        #--
        if options.autoindentAfterFunctionOrList:
            if event.keyval == 65293: # RETURN
                indent_triggers = {
                    '(': ')',
                    '{': '}',
                    '[': ']',
                    ':': '',
                }
                for indent_trigger, ending_char in indent_triggers.items():
                    if prev_char == indent_trigger:
                        if line_after:
                            # ...text between begin and ending brackets should come in the middle row.
                            if ending_char != '' and ending_char in line_after:
                                ending_pos = line_after.find(ending_char)
                            else:
                                ending_pos = len(line_after)
                            end = cursor.copy()
                            end.set_line_offset(end.get_line_offset() + ending_pos)
                            ending_text = doc.get_text(cursor, end, False).strip()
                            doc.delete(cursor, end)

                            add_middle = typed_char + whitespace + get_tab_string(view)
                            add_end = ending_text + typed_char + whitespace
                        else:
                            add_middle = typed_char + whitespace + get_tab_string(view)
                            add_end = ""
                        return self._insert_at_cursor(add_middle, add_end)


    def _insert_at_cursor(self, middle, end = ""):
        window = self.window
        doc = window.get_active_document()
        doc.insert_at_cursor(middle + end)
        #--
        # Refresh cursor and move it to the middle.
        #--
        cursor = doc.get_iter_at_mark(doc.get_insert())
        cursor.set_offset(cursor.get_offset() - len(end))
        doc.place_cursor(cursor)
        return True


#--
# Regular functions.
#--
def get_tab_string(view):
    tab_width = view.get_tab_width()
    tab_spaces = view.get_insert_spaces_instead_of_tabs()
    tab_code = ""
    if tab_spaces:
        for x in range(tab_width):
            tab_code += " "
    else:
        tab_code = "\t"
    return tab_code

def get_closing_xml_tag(document):
    tags = re.findall(r'<.*?>', document)
    tags.reverse()
    closed = []
    for tag in tags:
        # Ignore special tags like [<!-- --> and <!doctype ...>].
        if re.match(r'<!.*?>', tag):
            continue
        # Ignore special tags like [<?, <?=, <?php].
        if re.match(r'<\?.*?>', tag):
            continue
        # Neutral tag.
        if re.match(r'<.*?/>', tag):
            continue
        # Closing tag.
        m = re.match(r'</ *([^ ]*).*?>', tag)
        if m:
            closed.append(m.group(1))
            continue
        # Opening tag.
        m = re.match(r'< *([^/][^ ]*).*?>', tag)
        if m:
            openedtag = m.group(1)
            while True:
                if len(closed) == 0:
                    return openedtag
                close_tag = closed.pop()
                if close_tag.lower() == openedtag.lower():
                    break
            continue
    return None


#--
# OPTIONS DIALOG.
#--
class IntelligentTextCompletionOptions(object):

    # Settings:
    closeBracketsAndQuotes = True
    completeXML = True
    detectLists = True
    autoindentAfterFunctionOrList = True

    # Buttons for settings:
    _closeBracketsAndQuotesButton = None
    _completeXMLButton = None
    _detectListsButton = None
    _autoindentAfterFunctionOrListButton = None

    # Configuration client:
    _BASE_KEY = "apps.gedit-3.plugins.intelligent_text_completion"
    _settings = None

    # Static singleton reference:
    singleton = None

    def __init__(self):
        #--
        # Create settings directory if not set yet
        # self._settings = Gio.Settings.new(self._BASE_KEY)
        # if not self._gconf_client.dir_exists(self._GCONF_SETTINGS_DIR):
        # self._gconf_client.add_dir(self._GCONF_SETTINGS_DIR, gconf.CLIENT_PRELOAD_NONE).
        #--
        # Load settings.
        #--
        self.closeBracketsAndQuotes = self._load_setting("closeBracketsAndQuotes")
        self.completeXML = self._load_setting("completeXML")
        self.detectLists = self._load_setting("detectLists")
        self.autoindentAfterFunctionOrList = self._load_setting("autoindentAfterFunctionOrList")

    @classmethod
    def get_instance(cls):
        """
        Get singleton instance.
        """
        if cls.singleton is None:
            cls.singleton = cls()
        return cls.singleton

    def create_configure_dialog(self):
        """
        Creates configure dialog using GTK.
        """
        # Make vertically stacking box.
        vbox = Gtk.VBox()
        vbox.set_border_width(6)

        # Add warning.
        box = Gtk.HBox()
        label = Gtk.Label("Warning: these options are not yet persistent")
        box.pack_start(label, False, False, 6)
        vbox.pack_start(box, False, True, 0)

        # Add checkboxes.
        self._closeBracketsAndQuotesButton = self._add_setting_checkbox(
            vbox=vbox,
            current_value=self.closeBracketsAndQuotes,
            helptext="Auto-close brackets and quotes",
        )
        self._completeXMLButton = self._add_setting_checkbox(
            vbox=vbox,
            current_value=self.completeXML,
            helptext="Auto-complete XML tags",
        )
        self._detectListsButton = self._add_setting_checkbox(
            vbox=vbox,
            current_value=self.detectLists,
            helptext="Detect lists",
        )
        self._autoindentAfterFunctionOrListButton = self._add_setting_checkbox(
            vbox=vbox,
            current_value=self.autoindentAfterFunctionOrList,
            helptext="Auto-indent after function or list",
        )
        return vbox

    def _add_setting_checkbox(self, vbox, current_value, helptext):
        box = Gtk.HBox()
        check_button = Gtk.CheckButton(helptext)
        check_button.set_active(current_value)
        box.pack_start(check_button,False,False,6)
        check_button.connect('toggled', self._on_check_button_toggled)
        vbox.pack_start(box, False, True, 0)
        return check_button

    def _on_check_button_toggled(self, *args):
        # Set class attributes.
        self.closeBracketsAndQuotes = self._closeBracketsAndQuotesButton.get_active()
        self.completeXML = self._completeXMLButton.get_active()
        self.detectLists = self._detectListsButton.get_active()
        self.autoindentAfterFunctionOrList = self._autoindentAfterFunctionOrListButton.get_active()

        # Write changes to gconf.
        self._save_setting("closeBracketsAndQuotes", self.closeBracketsAndQuotes)
        self._save_setting("completeXML", self.completeXML)
        self._save_setting("detectLists", self.detectLists)
        self._save_setting("autoindentAfterFunctionOrList", self.autoindentAfterFunctionOrList)

    def _save_setting(self, setting_name, value):
        pass
        # self._gconf_client.set_bool("{}/{}".format(self._GCONF_SETTINGS_DIR, setting_name), value)

    def _load_setting(self, setting_name):
        return True
        # return self._gconf_client.get_bool("{}/{}".format(self._GCONF_SETTINGS_DIR, setting_name))

