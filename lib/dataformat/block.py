import time
import collections
import threading
import weakref

from exceptions import ObjectError, IntegrityError

class Block(object):
    """
    Smallest data unit for data management.
    """

    __slots__ = ['_name', '_dataset', 'id', '_size', '_num_files', 'is_open', 'replicas', 'last_update', '_files']

    _files_cache = collections.OrderedDict()
    _files_cache_lock = threading.Lock()
    _MAX_FILES_CACHE_DEPTH = 100
    _inventory_store = None

    @staticmethod
    def to_internal_name(name_str):
        # block name format: [8]-[4]-[4]-[4]-[12] where [n] is an n-digit hex.
        return long(name_str.replace('-', ''), 16)

    @staticmethod
    def to_real_name(name):
        full_string = hex(name).replace('0x', '')[:-1] # last character is 'L'
        if len(full_string) < 32:
            full_string = '0' * (32 - len(full_string)) + full_string

        return full_string[:8] + '-' + full_string[8:12] + '-' + full_string[12:16] + '-' + full_string[16:20] + '-' + full_string[20:]        

    @staticmethod
    def to_full_name(dataset_name, block_real_name):
        return dataset_name + '#' + block_real_name

    @staticmethod
    def from_full_name(full_name):
        # return dataset name, block internal name

        delim = full_name.find('#')
        if delim == -1:
            raise ObjectError('Invalid block name %s' % full_name)

        return full_name[:delim], Block.to_internal_name(full_name[delim + 1:])

    @property
    def name(self):
        return self._name

    @property
    def dataset(self):
        return self._dataset

    @property
    def num_files(self):
        return self._num_files

    @num_files.setter
    def num_files(self, value):
        if value != self._num_files:
            self._check_and_load_files(cache = False)
            self._num_files = value

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        if value != self._size:
            self._check_and_load_files(cache = False)
            self._size = value

    @property
    def files(self):
        return self._check_and_load_files()

    def __init__(self, name, dataset, size = 0, num_files = 0, is_open = False, last_update = 0, bid = 0, internal_name = True):
        if internal_name:
            self._name = name
        else:
            self._name = Block.to_internal_name(name)
        self._dataset = dataset
        self._size = size
        self._num_files = num_files
        self.is_open = is_open
        self.last_update = last_update
        
        self.id = bid

        self.replicas = set()

        self._files = None

    def __str__(self):
        replica_sites = '[%s]' % (','.join([r.site.name for r in self.replicas]))

        return 'Block %s (size=%d, num_files=%d, is_open=%s, last_update=%s, replicas=%s, id=%d)' % \
            (self.full_name(), self._size, self._num_files, self.is_open,
                time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.last_update)),
                replica_sites, self.id)

    def __repr__(self):
        # this representation cannot be directly eval'ed into a Block
        return 'Block(%s,%s,%d,%d,%s,%d,%d,False)' % \
            (repr(self.real_name()), repr(self._dataset_name()), self._size, self._num_files, self.is_open, self.last_update, self.id)

    def __eq__(self, other):
        return self is other or \
            (self._name == other._name and self._dataset_name() == other._dataset_name() and \
            self._size == other._size and self._num_files == other._num_files and \
            self.is_open == other.is_open and self.last_update == other.last_update)

    def __ne__(self, other):
        return not self.__eq__(other)

    def copy(self, other):
        if self._dataset_name() != other._dataset_name():
            raise ObjectError('Cannot copy a block of %s into a block of %s' % (other._dataset_name(), self._dataset_name()))

        self.is_open = other.is_open
        self.last_update = other.last_update

        if self._size != other._size or self._num_files != other._num_files:
            # updating file parameters -> need to load files permanently
            self._check_and_load_files(cache = False)
            self._size = other._size
            self._num_files = other._num_files

    def embed_into(self, inventory, check = False):
        try:
            dataset = inventory.datasets[self._dataset_name()]
        except KeyError:
            raise ObjectError('Unknown dataset %s' % self._dataset_name())

        block = dataset.find_block(self._name)
        updated = False
        if block is None:
            block = Block(self._name, dataset, self._size, self._num_files, self.is_open, self.last_update, self.id)
            dataset.blocks.add(block)
            updated = True
        elif check and (block is self or block == self):
            # identical object -> return False if check is requested
            pass
        else:
            block.copy(self)
            updated = True

        if check:
            return block, updated
        else:
            return block

    def unlink_from(self, inventory):
        try:
            dataset = inventory.datasets[self._dataset_name()]
            block = dataset.find_block(self._name, must_find = True)
        except (KeyError, ObjectError):
            return None

        block.unlink()
        return block

    def unlink(self):
        for replica in list(self.replicas):
            replica.unlink()

        # not unlinking individual files - they are not linked to anything other than this block

        self._dataset.blocks.remove(self)

        try:
            Block._files_cache.pop(self)
        except KeyError:
            pass

    def write_into(self, store):
        store.save_block(self)

    def delete_from(self, store):
        store.delete_block(self)

    def real_name(self):
        """
        Block._name can be in a converted internal format to save memory. This function returns the proper name.
        """

        return Block.to_real_name(self._name)

    def full_name(self):
        """
        Full specification of a block, including the dataset name.
        """

        return Block.to_full_name(self._dataset_name(), self.real_name())

    def find_file(self, lfn, must_find = False):
        """
        @param lfn        File name
        @param must_find  Raise an exception if file is not found.
        """
        try:
            return next(f for f in self.files if f._lfn == lfn)

        except StopIteration:
            if must_find:
                raise ObjectError('Cannot find file %s' % str(lfn))
            else:
                return None

    def add_file(self, lfile):
        """
        Add a file to self._files. This function does *not* increment _num_files or _size.
        """
        # make self._files a non-volatile set
        self._check_and_load_files(cache = False)
        self._files.add(lfile)

    def remove_file(self, lfile):
        """
        Remove a file from self._files. This function does *not* decrement _num_files or _size.
        """
        if lfile not in self.files:
            return

        # make self._files a non-volatile set
        self._check_and_load_files(cache = False)
        self._files.remove(lfile)

    def find_replica(self, site, must_find = False):
        try:
            if type(site) is str:
                return next(r for r in self.replicas if r.site.name == site)
            else:
                return next(r for r in self.replicas if r.site == site)

        except StopIteration:
            if must_find:
                raise ObjectError('Cannot find replica at %s for %s' % (site.name, self.full_name()))
            else:
                return None

    def _dataset_name(self):
        if type(self._dataset) is str:
            return self._dataset
        else:
            return self._dataset.name

    def _check_and_load_files(self, cache = True):
        if type(self._files) is set:
            return self._files

        with Block._files_cache_lock:
            if cache:
                if self._files is not None:
                    # self._files is either a real set (if _files was directly set), a valid weak proxy to a frozenset,
                    # or an expired weak proxy to a frozenset.
                    try:
                        len(self._files)
                    except ReferenceError:
                        # expired proxy
                        self._files = None
    
                if self._files is None:
                    while len(Block._files_cache) >= Block._MAX_FILES_CACHE_DEPTH:
                        # Keep _files_cache FIFO to Block._MAX_FILES_CACHE_DEPTH
                        Block._files_cache.popitem(last = False)

                    files = frozenset(self._load_files())
                    Block._files_cache[self] = files
                    self._files = weakref.proxy(files)

            else:
                if type(self._files) is weakref.ProxyType:
                    try:
                        self._files = set(self._files)
                    except ReferenceError:
                        # expired proxy
                        self._files = None

                    try:
                        Block._files_cache.pop(self)
                    except KeyError:
                        pass

                if self._files is None:
                    self._files = self._load_files()

            return self._files

    def _load_files(self):
        if self.id == 0:
            return set()

        files = Block._inventory_store.get_files(self)

        if len(files) != self._num_files:
            raise IntegrityError('Number of files mismatch in %s: predicted %d, loaded %d' % (str(self), self._num_files, len(files)))
        size = sum(f.size for f in files)
        if size != self._size:
            raise IntegrityError('Size mismatch in %s: predicted %d, loaded %d' % (str(self), self._size, size))

        return files
