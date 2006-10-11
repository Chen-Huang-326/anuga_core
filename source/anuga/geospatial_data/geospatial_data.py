"""Class Geospatial_data - Manipulation of locations on the planet and 
associated attributes.

"""

from os import access, F_OK, R_OK
from types import DictType

from Numeric import concatenate, array, Float, shape, reshape, ravel, take

from anuga.utilities.numerical_tools import ensure_numeric
from anuga.coordinate_transforms.geo_reference import Geo_reference, TitleError
from anuga.coordinate_transforms.redfearn import convert_from_latlon_to_utm

        
class Geospatial_data:

    def __init__(self,
                 data_points = None,
                 attributes = None,
                 geo_reference = None,
                 default_attribute_name = None,
                 file_name = None,
                 delimiter = None,
                 latitudes = None,
                 longitudes = None,
                 points_are_lats_longs = False,
                 verbose = False):

        
        """
        Create instance from data points and associated attributes

        data_points: x,y coordinates in meters. Type must be either a
        sequence of 2-tuples or an Mx2 Numeric array of floats.

        attributes: Associated values for each data point. The type
        must be either a list or an array of length M or a dictionary
        of lists (or arrays) of length M. In the latter case the keys
        in the dictionary represent the attribute names, in the former
        the attribute will get the default name "attribute".
        
        geo_reference: Object representing the origin of the data
        points. It contains UTM zone, easting and northing and data
        points are assumed to be relative to this origin.
        If geo_reference is None, the default geo ref object is used

        default_attribute_name: Name of default attribute to be used with
        get_attribute_values. The idea is that the dataset can be
        equipped with information about which attribute to return.
        If None, the default is the "first"
        
        file_name: Name of input netCDF file or xya file. netCDF file must 
        have dimensions "points" etc.
        xya file is a comma seperated file with x, y and attribute data. 
        the first line must be the attribute names eg elevation 
        
        The format for a .xya file is:
            1st line:     [attribute names]
            other lines:  x y [attributes]

            for example:
            elevation, friction
            0.6, 0.7, 4.9, 0.3
            1.9, 2.8, 5, 0.3
            2.7, 2.4, 5.2, 0.3

        The first two columns are always implicitly assumed to be x, y coordinates.
        Use the same delimiter for the attribute names and the data

        An xya file can optionally end with
            #geo reference
            56
            466600.0
            8644444.0

        When the 1st # is the zone,
        2nd # the xllcorner and 
        3rd # the yllcorner

        An issue with the xya format is that the attribute column order
        is not be controlled.  The info is stored in a dictionary and it's
        written however
        
        The format for a Points dictionary is:

          ['pointlist'] a 2 column array describing points. 1st column x, 2nd column y.
          ['attributelist'], a dictionary of 1D arrays, representing attribute values
          at the point.  The dictionary key is the attribute header.
          ['geo_reference'] a Geo_refernece object. Use if the point information
            is relative. This is optional.
            eg
            dic['pointlist'] = [[1.0,2.0],[3.0,5.0]]
            dic['attributelist']['elevation'] = [[7.0,5.0]
                
        delimiter: is the file delimiter that will be used when 
            importing the file
            
        verbose:
          
        """

        if isinstance(data_points, basestring):
            # assume data point is really a file name
            file_name = data_points

        self.set_verbose(verbose)
        self.geo_reference=None #create the attribute 
        if file_name is None:
            if delimiter is not None:
                msg = 'No file specified yet a delimiter is provided!'
                raise ValueError, msg
            file_name = None
            if latitudes is not None or longitudes is not None or \
                   points_are_lats_longs:
                data_points, geo_reference =  \
                             self._set_using_lat_long(latitudes=latitudes,
                                  longitudes=longitudes,
                                  geo_reference=geo_reference,
                                  data_points=data_points,
                                  points_are_lats_longs=points_are_lats_longs)
            self.check_data_points(data_points)
            self.set_attributes(attributes)
            self.set_geo_reference(geo_reference)
            self.set_default_attribute_name(default_attribute_name)

        else:
            # watch for case where file name and points, attributes etc are provided!!
            # if file name then all provided info will be removed!
            self.import_points_file(file_name, delimiter, verbose)
                
            self.check_data_points(self.data_points)
            self.set_attributes(self.attributes) 
            self.set_geo_reference(self.geo_reference)
            self.set_default_attribute_name(default_attribute_name)


        assert self.attributes is None or isinstance(self.attributes, DictType)
        

    def __len__(self):
        return len(self.data_points)

    def __repr__(self):
        return str(self.get_data_points(absolute=True))
    
    
    def check_data_points(self, data_points):
        """Checks data points
        """
        
        if data_points is None:
            self.data_points = None
            msg = 'There is no data or file provided!'
            raise ValueError, msg
            
        else:
            self.data_points = ensure_numeric(data_points)
            assert len(self.data_points.shape) == 2
            assert self.data_points.shape[1] == 2

    def set_attributes(self, attributes):
        """Check and assign attributes dictionary
        """
        
        if attributes is None:
            self.attributes = None
            return
        
        if not isinstance(attributes, DictType):
            #Convert single attribute into dictionary
            attributes = {'attribute': attributes}

        #Check input attributes    
        for key in attributes.keys():
            try:
                attributes[key] = ensure_numeric(attributes[key])
            except:
                msg = 'Attribute %s could not be converted' %key
                msg += 'to a numeric vector'
                raise msg

        self.attributes = attributes    


    def set_geo_reference(self, geo_reference):

        from anuga.coordinate_transforms.geo_reference import Geo_reference

        if geo_reference is None:
            geo_reference = Geo_reference() # Use default
        if not isinstance(geo_reference, Geo_reference):
            msg = 'Argument geo_reference must be a valid Geo_reference \n'
            msg += 'object or None.'
            raise msg

        # if a geo ref already exists, change the point data to
        # represent the new geo-ref
        if  self.geo_reference is not None:
            #FIXME: Maybe put out a warning here...
            self.data_points = self.get_data_points \
                               (geo_reference=geo_reference)
            
        self.geo_reference = geo_reference


    def set_default_attribute_name(self, default_attribute_name):
        self.default_attribute_name = default_attribute_name

    def set_verbose(self, verbose = False):
        if verbose is not False:
            verbose = True
        else:
            verbose = False

    def clip(self, polygon, closed=True):
        """Clip geospatial data by a polygon

        Input
          polygon - Either a list of points, an Nx2 array or
                    a Geospatial data object.
          closed - (optional) determine whether points on boundary should be
          regarded as belonging to the polygon (closed = True)
          or not (closed = False). Default is True.
          
        Output
          New geospatial data object representing points inside
          specified polygon.
        
        """

        from anuga.utilities.polygon import inside_polygon

        if isinstance(polygon, Geospatial_data):
            # Polygon is an object - extract points
            polygon = polygon.get_data_points()

        points = self.get_data_points()    
        inside_indices = inside_polygon(points, polygon, closed)

        clipped_points = take(points, inside_indices)

        # Clip all attributes
        attributes = self.get_all_attributes()

        clipped_attributes = {}
        if attributes is not None:
            for key, att in attributes.items():
                clipped_attributes[key] = take(att, inside_indices)

        return Geospatial_data(clipped_points, clipped_attributes)
        
        
    def clip_outside(self, polygon, closed=True):
        """Clip geospatial date by a polygon, keeping data OUTSIDE of polygon

        Input
          polygon - Either a list of points, an Nx2 array or
                    a Geospatial data object.
          closed - (optional) determine whether points on boundary should be
          regarded as belonging to the polygon (closed = True)
          or not (closed = False). Default is True.
          
        Output
          Geospatial data object representing point OUTSIDE specified polygon
        
        """

        from anuga.utilities.polygon import outside_polygon

        if isinstance(polygon, Geospatial_data):
            # Polygon is an object - extract points
            polygon = polygon.get_data_points()

        points = self.get_data_points()    
        outside_indices = outside_polygon(points, polygon, closed)

        clipped_points = take(points, outside_indices)

        # Clip all attributes
        attributes = self.get_all_attributes()

        clipped_attributes = {}
        if attributes is not None:
            for key, att in attributes.items():
                clipped_attributes[key] = take(att, outside_indices)

        return Geospatial_data(clipped_points, clipped_attributes)

    
    def _set_using_lat_long(self,
                            latitudes,
                            longitudes,
                            geo_reference,
                            data_points,
                            points_are_lats_longs):
        
        if geo_reference is not None:
            msg = """A georeference is specified yet latitude and longitude
            are also specified!"""
            raise ValueError, msg
        
        if data_points is not None and not points_are_lats_longs:
            msg = """Data points are specified yet latitude and
            longitude are also specified!"""
            raise ValueError, msg
        
        if points_are_lats_longs:
            if data_points is None:
                msg = """Data points are not specified !"""
                raise ValueError, msg
            lats_longs = ensure_numeric(data_points)
            latitudes = ravel(lats_longs[:,0:1])
            longitudes = ravel(lats_longs[:,1:])
            
        if latitudes is None and longitudes is None:
            msg = """Latitudes and Longitudes are not."""
            raise ValueError, msg
        
        if latitudes is None:
            msg = """Longitudes are specified yet latitudes aren't!"""
            raise ValueError, msg
        
        if longitudes is None:
            msg = """Latitudes are specified yet longitudes aren't!"""
            raise ValueError, msg
        
        data_points, zone  = convert_from_latlon_to_utm(latitudes=latitudes,
                                                        longitudes=longitudes)
        
        return data_points, Geo_reference(zone=zone)
    
    def get_geo_reference(self):
        return self.geo_reference
       
    def get_data_points(self, absolute = True, geo_reference=None):
        """Get coordinates for all data points as an Nx2 array

        If absolute is True absolute UTM coordinates are returned otherwise
        returned coordinates are relative to the internal georeference's
        xll and yll corners.

        If a geo_reference is passed the points are returned relative
        to that geo_reference.

        Default: absolute is True.
        """

        if absolute is True and geo_reference is None:
            return self.geo_reference.get_absolute(self.data_points)
        elif geo_reference is not None:
            return geo_reference.change_points_geo_ref \
                               (self.data_points, 
                                self.geo_reference)
        else:
            return self.data_points
        
    
    def get_attributes(self, attribute_name = None):
        """Return values for one named attribute.

        If attribute_name is None, default_attribute_name is used
        """

        if attribute_name is None:
            if self.default_attribute_name is not None:
                attribute_name = self.default_attribute_name
            else:
                attribute_name = self.attributes.keys()[0] 
                # above line takes the first one from keys
                

        msg = 'Attribute name %s does not exist in data set' %attribute_name
        assert self.attributes.has_key(attribute_name), msg

        return self.attributes[attribute_name]

    def get_all_attributes(self):
        """
        Return values for all attributes.
        The return value is either None or a dictionary (possibly empty).
        """

        return self.attributes

    def __add__(self, other):
        """
        Returns the addition of 2 geospatical objects,
        objects are concatencated to the end of each other
            
        NOTE: doesn't add if objects contain different 
        attributes  
        
        Always return relative points!
        """

        # find objects zone and checks if the same
        geo_ref1 = self.get_geo_reference()
        zone1 = geo_ref1.get_zone()
        
        geo_ref2 = other.get_geo_reference()
        zone2 = geo_ref2.get_zone()

        geo_ref1.reconcile_zones(geo_ref2)


        # sets xll and yll as the smallest from self and other
        # FIXME (Duncan and Ole): use lower left corner derived from
        # absolute coordinates
        if self.geo_reference.xllcorner <= other.geo_reference.xllcorner:
            xll = self.geo_reference.xllcorner
        else:
            xll = other.geo_reference.xllcorner

        if self.geo_reference.yllcorner <= other.geo_reference.yllcorner:
            yll = self.geo_reference.yllcorner
        else:
            yll = other.geo_reference.yllcorner
        new_geo_ref = Geo_reference(geo_ref1.get_zone(), xll, yll)

        xll = yll = 0. 
        
        relative_points1 = self.get_data_points(absolute = False)
        relative_points2 = other.get_data_points(absolute = False)

        
        new_relative_points1 = new_geo_ref.\
                               change_points_geo_ref(relative_points1,
                                                     geo_ref1)
        new_relative_points2 = new_geo_ref.\
                               change_points_geo_ref(relative_points2,
                                                     geo_ref2)
        
        # Now both point sets are relative to new_geo_ref and
        # zones have been reconciled

        # Concatenate points
        new_points = concatenate((new_relative_points1,
                                  new_relative_points2),
                                  axis = 0)
      
        # Concatenate attributes if any
        if self.attributes is None:
            if other.attributes is not None:
                msg = 'Both geospatial_data objects must have the same \n'
                msg += 'attributes to allow addition.'
                raise Exception, msg
            
            new_attributes = None
        else:    
            new_attributes = {}
            for x in self.attributes.keys():
                if other.attributes.has_key(x):

                    attrib1 = self.attributes[x]
                    attrib2 = other.attributes[x]
                    new_attributes[x] = concatenate((attrib1, attrib2))

                else:
                    msg = 'Both geospatial_data objects must have the same \n'
                    msg += 'attributes to allow addition.'
                    raise Exception, msg

        # Instantiate new data object and return    
        return Geospatial_data(new_points,
                               new_attributes,
                               new_geo_ref)
    
    ###
    #  IMPORT/EXPORT POINTS FILES
    ###

    def import_points_file(self, file_name, delimiter = None, verbose = False):
        """ load an .xya or .pts file
        Note: will throw an IOError if it can't load the file.
        Catch these!

        Post condition: self.attributes dictionary has been set
        """
        
        if access(file_name, F_OK) == 0 :
            msg = 'File %s does not exist or is not accessible' %file_name
            raise IOError, msg
        
        attributes = {}
        if file_name[-4:]== ".xya":
            try:
                if delimiter == None:
                    try:
                        fd = open(file_name)
                        data_points, attributes, geo_reference = _read_xya_file(fd, ',')
                    except TitleError:
                        fd.close()
                        fd = open(file_name)
                        data_points, attributes, geo_reference = _read_xya_file(fd, ' ')
                else:
                    fd = open(file_name)
                    data_points, attributes, geo_reference = _read_xya_file(fd, delimiter)
                fd.close()
            except (IndexError,ValueError,SyntaxError):
                fd.close()    
                msg = 'Could not open file %s ' %file_name
                raise IOError, msg
            except IOError, e:
                fd.close()  
                # Catch this to add an error message
                msg = 'Could not open file or incorrect file format %s:%s' %(file_name, e)
                raise IOError, msg
                
        elif file_name[-4:]== ".pts":
            try:
                data_points, attributes, geo_reference = _read_pts_file(file_name, verbose)
            except IOError, e:    
                msg = 'Could not open file %s ' %file_name
                raise IOError, msg        
        else:      
            msg = 'Extension %s is unknown' %file_name[-4:]
            raise IOError, msg
        
#        print'in import data_points', data_points
#        print'in import attributes', attributes
#        print'in import data_points', geo_reference
        self.data_points = data_points
        self.attributes = attributes
        self.geo_reference = geo_reference
    
#        return all_data
    
    def export_points_file(self, file_name, absolute=True):
        
        """
        write a points file, file_name, as a text (.xya) or binary (.pts) file
        file_name is the file name, including the extension
        The point_dict is defined at the top of this file.
        
        If absolute is True data points at returned added to the xll and yll 
        and geo_reference as None
        
        If absolute is False data points at returned as relative to the xll 
        and yll and geo_reference remains uneffected
        """
    
        if (file_name[-4:] == ".xya"):
            if absolute is True:         
                _write_xya_file(file_name,
                                self.get_data_points(absolute=True), 
                                self.get_all_attributes())
            else:
                _write_xya_file(file_name,
                                self.get_data_points(absolute=False), 
                                self.get_all_attributes(),
                                self.get_geo_reference())
                                    
        elif (file_name[-4:] == ".pts"):
            if absolute is True:
                _write_pts_file(file_name,
                                self.get_data_points(absolute), 
                                self.get_all_attributes())
            else:
                _write_pts_file(file_name,
                                self.get_data_points(absolute), 
                                self.get_all_attributes(),
                                self.get_geo_reference())
        else:
            msg = 'Unknown file type %s ' %file_name
            raise IOError, msg 
    



def _read_pts_file(file_name, verbose = False):
    """Read .pts NetCDF file
    
    Return a dic of array of points, and dic of array of attribute
    eg
    dic['points'] = [[1.0,2.0],[3.0,5.0]]
    dic['attributelist']['elevation'] = [[7.0,5.0]
    """    

    from Scientific.IO.NetCDF import NetCDFFile
    
    if verbose: print 'Reading ', file_name
    
        
    # see if the file is there.  Throw a QUIET IO error if it isn't
    fd = open(file_name,'r')
    fd.close()
    
    #throws prints to screen if file not present
    fid = NetCDFFile(file_name, 'r') 
    
#    point_atts = {}  
        # Get the variables
#    point_atts['pointlist'] = array(fid.variables['points'])
    pointlist = array(fid.variables['points'])
    keys = fid.variables.keys()
    if verbose: print 'Got %d variables: %s' %(len(keys), keys)
    try:
        keys.remove('points')
    except IOError, e:       
        fid.close()    
        msg = 'Expected keyword "points" but could not find it'
        raise IOError, msg
    
    attributes = {}
    for key in keys:
        if verbose: print "reading attribute '%s'" %key
            
        attributes[key] = array(fid.variables[key])
    
#    point_atts['attributelist'] = attributes
    
    try:
        geo_reference = Geo_reference(NetCDFObject=fid)
#        point_atts['geo_reference'] = geo_reference
    except AttributeError, e:
        #geo_ref not compulsory 
#        point_atts['geo_reference'] = None
        geo_reference = None
    
    fid.close()
    
    return pointlist, attributes, geo_reference


def _read_xya_file( fd, delimiter):
    points = []
    pointattributes = []
    title = fd.readline()
    att_names = clean_line(title,delimiter)
    att_dict = {}
    line = fd.readline()
    numbers = clean_line(line,delimiter)
    
    while len(numbers) > 1 and line[0] <> '#':
        if numbers != []:
            try:
                x = float(numbers[0])
                y = float(numbers[1])
                points.append([x,y])
                numbers.pop(0)
                numbers.pop(0)
                if len(att_names) != len(numbers):
                    fd.close()
                    # It might not be a problem with the title
                    #raise TitleAmountError
                    raise IOError
                for i,num in enumerate(numbers):
                    num.strip()
                    if num != '\n' and num != '':
                        #attributes.append(float(num))
                        att_dict.setdefault(att_names[i],[]).append(float(num))
            except ValueError:
                raise SyntaxError
        line = fd.readline()
        numbers = clean_line(line,delimiter)
    
    if line == '':
        geo_reference = None
    else:
        geo_reference = Geo_reference(ASCIIFile=fd,read_title=line)
        
    
    pointlist = array(points).astype(Float)
    for key in att_dict.keys():
        att_dict[key] = array(att_dict[key]).astype(Float)
    
    return pointlist, att_dict, geo_reference

def _write_pts_file(file_name,
                    write_data_points,
                    write_attributes=None, 
                    write_geo_reference=None):
    """
    Write .pts NetCDF file   

    NOTE: Below might not be valid ask Duncan : NB 5/2006
    
    WARNING: This function mangles the point_atts data structure
    #F??ME: (DSG)This format has issues.
    # There can't be an attribute called points 
    # consider format change
    # method changed by NB not sure if above statement is correct
    
    should create new test for this
    legal_keys = ['pointlist', 'attributelist', 'geo_reference']
    for key in point_atts.keys():
        msg = 'Key %s is illegal. Valid keys are %s' %(key, legal_keys) 
        assert key in legal_keys, msg
    """    
    from Scientific.IO.NetCDF import NetCDFFile
    # NetCDF file definition
    outfile = NetCDFFile(file_name, 'w')
    
    #Create new file
    outfile.institution = 'Geoscience Australia'
    outfile.description = 'NetCDF format for compact and portable storage ' +\
                          'of spatial point data'
    
    # dimension definitions
    shape = write_data_points.shape[0]
    outfile.createDimension('number_of_points', shape)  
    outfile.createDimension('number_of_dimensions', 2) #This is 2d data
    
    # variable definition
    outfile.createVariable('points', Float, ('number_of_points',
                                             'number_of_dimensions'))

    #create variables  
    outfile.variables['points'][:] = write_data_points #.astype(Float32)

    if write_attributes is not None:
        for key in write_attributes.keys():
            outfile.createVariable(key, Float, ('number_of_points',))
            outfile.variables[key][:] = write_attributes[key] #.astype(Float32)
        
    if write_geo_reference is not None:
        write_geo_reference.write_NetCDF(outfile)
        
    outfile.close() 
  


def _write_xya_file(file_name,
                    write_data_points,
                    write_attributes=None, 
                    write_geo_reference=None, 
                    delimiter = ','):
    """
    export a file, file_name, with the xya format
    
    """
    points = write_data_points 
    pointattributes = write_attributes
    
    fd = open(file_name,'w')
    titlelist = ""
    if pointattributes is not None:    
        for title in pointattributes.keys():
            titlelist = titlelist + title + delimiter
        titlelist = titlelist[0:-len(delimiter)] # remove the last delimiter
    fd.write(titlelist+"\n")
    
    #<vertex #> <x> <y> [attributes]
    for i, vert in enumerate( points):


        if pointattributes is not None:            
            attlist = ","
            for att in pointattributes.keys():
                attlist = attlist + str(pointattributes[att][i])+ delimiter
            attlist = attlist[0:-len(delimiter)] # remove the last delimiter
            attlist.strip()
        else:
            attlist = ''

        fd.write(str(vert[0]) + delimiter +
                 str(vert[1]) + attlist + "\n")

    if  write_geo_reference is not None:
        write_geo_reference.write_ASCII(fd)
    fd.close()


    
def _point_atts2array(point_atts):
    point_atts['pointlist'] = array(point_atts['pointlist']).astype(Float)
    
    for key in point_atts['attributelist'].keys():
        point_atts['attributelist'][key]= array(point_atts['attributelist'][key]).astype(Float)
    return point_atts

   


def geospatial_data2points_dictionary(geospatial_data):
    """Convert geospatial data to points_dictionary
    """

    points_dictionary = {}
    points_dictionary['pointlist'] = geospatial_data.data_points

    points_dictionary['attributelist'] = {}

    for attribute_name in geospatial_data.attributes.keys():
        val = geospatial_data.attributes[attribute_name]
        points_dictionary['attributelist'][attribute_name] = val

    points_dictionary['geo_reference'] = geospatial_data.geo_reference

    return points_dictionary

    
def points_dictionary2geospatial_data(points_dictionary):
    """Convert points_dictionary to geospatial data object
    """

    msg = 'Points dictionary must have key pointlist' 
    assert points_dictionary.has_key('pointlist'), msg

    msg = 'Points dictionary must have key attributelist'     
    assert points_dictionary.has_key('attributelist'), msg        

    if points_dictionary.has_key('geo_reference'):
        geo = points_dictionary['geo_reference']
    else:
        geo = None
    
    return Geospatial_data(points_dictionary['pointlist'],
                           points_dictionary['attributelist'],
                           geo_reference = geo)

def clean_line(line,delimiter):      
    """Remove whitespace
    """
    #print ">%s" %line
    line = line.strip()
    #print "stripped>%s" %line
    numbers = line.split(delimiter)
    i = len(numbers) - 1
    while i >= 0:
        if numbers[i] == '':
            numbers.pop(i)
        else:
            numbers[i] = numbers[i].strip()
        
        i += -1
    #for num in numbers:
    #    print "num>%s<" %num
    return numbers
            
def xxx_add_points_files(add_file1, add_file2, results_file):
    """ adds the points and attruibutes of 2 pts or xya files and
    writes it to a pts file
    
    NOTE will add the function to check and remove points from one set
    that are shared. This will require some work and maybe __subtract__ function 
    """
    
    G1 = Geospatial_data(file_name = add_file1)
    G2 = Geospatial_data(file_name = add_file2)
    new_add_file2 = add_file2[:-4] + '.pts' 

    G = G1 + G2
    
    #FIXME remove dependance on points to dict in export only!
#    G_points_dict = geospatial_data2points_dictionary(G)
#    export_points_file(results_file, G_points_dict)

#    G_points_dict = geospatial_data2points_dictionary(G)

    G.export_points_file(results_file)

# '
def ensure_absolute(points, geo_reference = None):
    """
    This function inputs several formats and
    outputs one format. - a numeric array of absolute points.

    Inputed formats are;
    points: List or numeric array of coordinate pairs [xi, eta] of
	      points or geospatial object or points file name

    mesh_origin: A geo_reference object or 3-tuples consisting of
                 UTM zone, easting and northing.
                 If specified vertex coordinates are assumed to be
                 relative to their respective origins.
    """
    if isinstance(points,type('')):
        #It's a string
        #assume it is a point file
        points = Geospatial_data(file_name = points)
        
    if isinstance(points,Geospatial_data):
        points = points.get_data_points( \
                absolute = True)
        msg = "Use a Geospatial_data object or a mesh origin. Not both."
        assert geo_reference == None, msg
            
    else:
        points = ensure_numeric(points, Float)
    if geo_reference is None:
        geo = None #Geo_reference()
    else:
        if isinstance(geo_reference, Geo_reference):
            geo = geo_reference
        else:
            geo = Geo_reference(geo_reference[0],
                                geo_reference[1],
                                geo_reference[2])
        points = geo.get_absolute(points)
    return points
     

def ensure_geospatial(points, geo_reference = None):
    """
    This function inputs several formats and
    outputs one format. - a geospatial_data instance.

    Inputed formats are;
    points: List or numeric array of coordinate pairs [xi, eta] of
	      points or geospatial object

    mesh_origin: A geo_reference object or 3-tuples consisting of
                 UTM zone, easting and northing.
                 If specified vertex coordinates are assumed to be
                 relative to their respective origins.
    """
    if isinstance(points,Geospatial_data):
        msg = "Use a Geospatial_data object or a mesh origin. Not both."
        assert geo_reference == None, msg
        return points    
    else:
        points = ensure_numeric(points, Float)
    if geo_reference is None:
        geo = None
    else:
        if isinstance(geo_reference, Geo_reference):
            geo = geo_reference
        else:
            geo = Geo_reference(geo_reference[0],
                                geo_reference[1],
                                geo_reference[2])
    points = Geospatial_data(data_points=points, geo_reference=geo)        
    return points
             
